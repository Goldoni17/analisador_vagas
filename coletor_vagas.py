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
LOCAL = "São Paulo, Brasil" # Foco em SP e Remotas
ARQUIVO_DADOS = 'vagas.json'
LIMITE_VAGAS_POR_CARGO = 5 

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
    
    # Busca nas 3 primeiras páginas para garantir vagas suficientes
    for inicio in [0, 25, 50]:
        url_busca = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={cargo_url}&location={urllib.parse.quote(LOCAL)}&start={inicio}"
        resposta = requests.get(url_busca, headers=HEADERS)
        site = BeautifulSoup(resposta.text, 'html.parser')
        
        links_pagina = [card['href'].split('?')[0] for card in site.find_all('a', class_='base-card__full-link')]
        links_totais.extend(links_pagina)
        time.sleep(2)
        
    links_unicos = list(set(links_totais))
    print(f"✅ Encontramos {len(links_unicos)} vagas nas 3 primeiras páginas para {cargo}.")
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
    Você é um recrutador técnico. Leia a descrição da vaga e extraia os dados.
    
    Regras estritas:
    1. Responda APENAS com JSON válido.
    2. hard_skills: identifique ferramentas, linguagens e frameworks (exclua soft skills).
    3. ingles: use APENAS "Obrigatório", "Desejável" ou "Não mencionado".
    4. modelo_trabalho: identifique se a vaga é "Remoto", "Híbrido", "Presencial". Se não der para saber, use "Não mencionado".
    
    Formato esperado:
    {{
        "hard_skills": ["Python", "AWS", "SQL"],
        "ingles": "Obrigatório",
        "modelo_trabalho": "Remoto"
    }}
    
    Descrição da vaga:
    {texto_vaga}
    """
    
    tentativas = 0
    while tentativas < 3:
        try:
            resposta = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
            texto_limpo = resposta.text.replace("```json", "").replace("```", "").strip()
            return json.loads(texto_limpo)
            
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print("      ⏳ Limite da API atingido. Dormindo por 60s...")
                time.sleep(60) 
                tentativas += 1
            else:
                return {"hard_skills": [], "ingles": "Não mencionado", "modelo_trabalho": "Não mencionado"}
                
    return {"hard_skills": [], "ingles": "Não mencionado", "modelo_trabalho": "Não mencionado"}

# ================= EXECUÇÃO =================
if __name__ == '__main__':
    vagas_processadas = carregar_dados_antigos()
    urls_ja_analisadas = {v['url'] for v in vagas_processadas}
    
    # NOVA REGRA: Deduplicação por Título + Empresa
    assinaturas_ja_analisadas = {f"{v['titulo']} - {v['empresa']}" for v in vagas_processadas}
    
    novas_vagas_adicionadas = 0

    for cargo_atual in CARGOS:
        links = pegar_links_das_vagas(cargo_atual)
        vagas_novas_neste_cargo = 0
        
        for link in links:
            if vagas_novas_neste_cargo >= LIMITE_VAGAS_POR_CARGO:
                print(f"🛑 Limite de {LIMITE_VAGAS_POR_CARGO} vagas atingido para {cargo_atual}.")
                break
                
            if link in urls_ja_analisadas:
                continue 
                
            print(f"Lendo vaga nova: {link}...")
            dados = extrair_descricao_da_vaga(link, cargo_atual)
            
            if dados:
                assinatura = f"{dados['titulo']} - {dados['empresa']}"
                if assinatura in assinaturas_ja_analisadas:
                    print("   -> ♻️ Vaga duplicada (mesmo cargo e empresa em outro link). Ignorando...")
                    urls_ja_analisadas.add(link)
                    continue

                skills = extrair_skills_com_ia(dados['descricao'])
                
                # NOVA REGRA: Só salva se a IA encontrou alguma Hard Skill
                if not skills.get('hard_skills') or len(skills.get('hard_skills')) == 0:
                    print("   -> ❌ Vaga sem Hard Skills (descrição vazia ou genérica). Descartando...")
                    urls_ja_analisadas.add(link)
                    time.sleep(5)
                    continue

                dados.update(skills)
                if 'descricao' in dados: del dados['descricao'] 
                
                vagas_processadas.append(dados)
                urls_ja_analisadas.add(link)
                assinaturas_ja_analisadas.add(assinatura)
                
                novas_vagas_adicionadas += 1
                vagas_novas_neste_cargo += 1
                
                print(f"   -> 🧠 Skills: {', '.join(dados['hard_skills'][:5])}...")
                print(f"   -> 🌎 Inglês: {dados.get('ingles')} | 🏢 Modelo: {dados.get('modelo_trabalho')}")
            
            time.sleep(5)
            
    if novas_vagas_adicionadas > 0:
        with open(ARQUIVO_DADOS, 'w', encoding='utf-8') as arquivo:
            json.dump(vagas_processadas, arquivo, ensure_ascii=False, indent=4)
        print(f"\n🎉 Concluído! {novas_vagas_adicionadas} vagas novas e validadas foram adicionadas.")
    else:
        print("\n🎉 Concluído! Nenhuma vaga válida e inédita hoje.")
