import streamlit as st
import pandas as pd
import json
from collections import Counter
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Tech Recruiter AI", layout="wide")
st.title("📊 Radar de Vagas: IA e Dados")
st.markdown("Monitoramento automatizado das exigências do mercado de tecnologia.")

try:
    with open('vagas.json', 'r', encoding='utf-8') as f:
        vagas = json.load(f)
except FileNotFoundError:
    st.error("Arquivo de dados não encontrado.")
    st.stop()

if not vagas:
    st.warning("O banco de dados está vazio no momento.")
    st.stop()

# ================= FILTRO =================
st.sidebar.header("Filtros")
cargos = list(set([v['categoria'] for v in vagas]))
cargo_selecionado = st.sidebar.selectbox("Filtre por Profissão:", ["Todos"] + cargos)

if cargo_selecionado == "Todos":
    vagas_filtradas = vagas
else:
    vagas_filtradas = [v for v in vagas if v['categoria'] == cargo_selecionado]

# ================= MÉTRICAS =================
hoje = datetime.now().strftime('%Y-%m-%d')
total_historico = len(vagas_filtradas)
vagas_hoje = len([v for v in vagas_filtradas if v.get('data_coleta') == hoje])

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Total de Vagas Analisadas", total_historico)
col_m2.metric("Vagas Novas Hoje", vagas_hoje)
col_m3.metric("Cargos Monitorados", len(cargos) if cargo_selecionado == "Todos" else 1)

st.markdown("---")

# ================= PROCESSAMENTO DOS GRÁFICOS =================
hard_skills = []
ingles_status = []

for v in vagas_filtradas:
    hard_skills.extend(v.get('hard_skills', []))
    ingles = v.get('ingles', 'Não mencionado')
    ingles_status.append(ingles if ingles in ["Obrigatório", "Desejável"] else "Não mencionado")

top_hard = Counter(hard_skills).most_common(15)

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("💻 Top 15 Hard Skills")
    if top_hard:
        df_hard = pd.DataFrame(top_hard, columns=["Skill", "Menções"])
        fig_hard = px.bar(df_hard, x="Menções", y="Skill", orientation='h', color_discrete_sequence=['#00b4d8'])
        fig_hard.update_yaxes(categoryorder="total ascending")
        st.plotly_chart(fig_hard, use_container_width=True)

with col2:
    st.subheader("🌎 Exigência de Inglês")
    if ingles_status:
        df_ingles = pd.DataFrame(ingles_status, columns=["Nível"])
        contagem_ingles = df_ingles['Nível'].value_counts().reset_index()
        contagem_ingles.columns = ['Nível', 'Quantidade']
        
        cores_ingles = {'Obrigatório': '#d62828', 'Desejável': '#f77f00', 'Não mencionado': '#8d99ae'}
        fig_ingles = px.pie(contagem_ingles, values='Quantidade', names='Nível', hole=0.4, color='Nível', color_discrete_map=cores_ingles)
        st.plotly_chart(fig_ingles, use_container_width=True)

# ================= LISTA DE VAGAS RECENTES =================
st.markdown("---")
st.subheader("📝 Últimas Vagas Capturadas")

# Ordena para mostrar as mais recentes primeiro e pega as top 20
vagas_ordenadas = sorted(vagas_filtradas, key=lambda x: x.get('data_coleta', ''), reverse=True)[:20]

for v in vagas_ordenadas:
    with st.expander(f"{v['data_coleta']} | {v['titulo']} - {v['empresa']}"):
        st.write(f"**🔗 Link:** [Acessar vaga no LinkedIn]({v['url']})")
        st.write(f"**🛠️ Hard Skills:** {', '.join(v.get('hard_skills', []))}")
        st.write(f"**🌎 Inglês:** {v.get('ingles', 'Não mencionado')}")