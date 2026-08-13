import requests
from bs4 import BeautifulSoup
import time
import urllib.parse
from google import genai
import json
import os
from datetime import datetime

# ================= CONFIGURAÇÕES =================
CARGOS = ["Data Scientist", "AI Engineer", "Desenvolvedor Python"]
LOCAL = "Brasil"
ARQUIVO_DADOS = 'vagas.json'

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

CHAVE_API = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=CHAVE_API)
# =================================================

def carregar_dados_antigos():
    if os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def pegar_links_das_vagas(cargo):
    print(f"\n🔍 Buscando vagas de {cargo} em {LOCAL}...")
    cargo_url = urllib.parse.quote(cargo)
    links_totais = []
    
    # Busca nas duas primeiras páginas (0 e 25) para pegar mais vagas
    for inicio in [0, 25]:
        url_busca = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={cargo_url}&location={LOCAL}&start={inicio}"
        resposta = requests.get(url_busca, headers=HEADERS)
        site = BeautifulSoup(resposta.text, 'html.parser')
        
        links_pagina = [card['href'].split('?')[0] for card in site.find_all('a', class_='base-card__full-link')]
        links_totais.extend(links_pagina)
        time.sleep(2)
        
    # Remove duplicatas da própria busca
    links_unicos = list(set(links_totais))
    print(f"✅ Encontramos {len(links_unicos)} vagas únicas para {cargo}.")
    return links_unicos

def extrair_descricao_da_vaga(url_vaga, cargo_buscado):
    resposta = requests.get(url_vaga, headers=HEADERS)
    if "authwall" in resposta.url or "login" in resposta.url:
        return None
        
    site = BeautifulSoup(resposta.text, 'html.parser')
    try:
        titulo_tag = site.find('h1', class_='top-card-layout__title') or site.find('h2', class_='top-card-layout__title')
        empresa_tag = site.find('a', class_='topcard__org-name-link') or site.find('span', class_='topcard__flavor')
        descricao_html = site.find('div', class_='show-more-less-html__markup') or site.find('div', class_='description__text') or site.find('div', class_='core-section-container__content')
        
        if not (titulo_tag and empresa_tag and descricao_html):
            return None
            
        return {
            "categoria": cargo_buscado, 
            "titulo": titulo_tag.text.strip(),
            "empresa": empresa_tag.text.strip(),
            "descricao": descricao_html.get_text(separator='\n').strip(),
            "url": url_vaga,
            "data_coleta": datetime.now().strftime('%Y-%m-%d')
        }
    except Exception:
        return None

def extrair_skills_com_ia(texto_vaga):
    prompt = f"""
    Você é um recrutador técnico. Leia a descrição da vaga e extraia os dados abaixo.
    
    Regras estritas:
    1. Responda APENAS com JSON válido.
    2. Identifique hard skills (ferramentas, linguagens, frameworks). Não inclua soft skills.
    3. Identifique a exigência de Inglês. Use APENAS uma destas três opções exatas: "Obrigatório", "Desejável", ou "Não mencionado".
    
    Formato esperado:
    {{
        "hard_skills": ["skill1", "skill2"],
        "ingles": "Obrigatório"
    }}
    
    Descrição:
    {texto_vaga}
    """
    
    tentativas = 0
    while tentativas < 3:
        try:
            resposta = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt
            )
            texto_limpo = resposta.text.replace("```json", "").replace("```", "").strip()
            return json.loads(texto_limpo)
            
        except Exception as e:
            erro_str = str(e)
            if "429" in erro_str or "RESOURCE_EXHAUSTED" in erro_str:
                print("      ⏳ Limite da API atingido. O robô vai dormir por 60 segundos...")
                time.sleep(60) 
                tentativas += 1
            else:
                print(f"      ⚠️ Erro na IA: {e}")
                return {"hard_skills": [], "ingles": "Não mencionado"}
                
    return {"hard_skills": [], "ingles": "Não mencionado"}

# ================= EXECUÇÃO =================
if __name__ == '__main__':
    vagas_processadas = carregar_dados_antigos()
    urls_ja_analisadas = {v['url'] for v in vagas_processadas}
    
    novas_vagas_adicionadas = 0

    for cargo_atual in CARGOS:
        links = pegar_links_das_vagas(cargo_atual)
        
        for link in links:
            # Se a vaga já estiver no nosso JSON, ele pula para o próximo link
            if link in urls_ja_analisadas:
                continue 
                
            print(f"Lendo vaga nova: {link}...")
            dados = extrair_descricao_da_vaga(link, cargo_atual)
            
            if dados:
                skills = extrair_skills_com_ia(dados['descricao'])
                dados.update(skills)
                
                # Remove o texto cru para o arquivo não ficar gigante
                if 'descricao' in dados:
                    del dados['descricao'] 
                
                vagas_processadas.append(dados)
                urls_ja_analisadas.add(link)
                novas_vagas_adicionadas += 1
                
                print(f"   -> 🧠 Hard Skills: {', '.join(dados.get('hard_skills', []))}")
                print(f"   -> 🌎 Inglês: {dados.get('ingles', 'Não mencionado')}")
            
            # PAUSA CORRETA: Dentro do loop das vagas, para esperar 5s antes de ir para o próximo link
            time.sleep(5)
            
    # SALVAMENTO CORRETO: Fora de todos os loops. Só salva depois que ler absolutamente tudo.
    if novas_vagas_adicionadas > 0:
        with open(ARQUIVO_DADOS, 'w', encoding='utf-8') as arquivo:
            json.dump(vagas_processadas, arquivo, ensure_ascii=False, indent=4)
        print(f"\n🎉 Concluído! {novas_vagas_adicionadas} vagas novas foram adicionadas ao banco de dados.")
    else:
        print("\n🎉 Concluído! Nenhuma vaga nova hoje. O banco de dados já está atualizado.")
