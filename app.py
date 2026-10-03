import streamlit as st
import pandas as pd
import json
from collections import Counter
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Tech Recruiter AI", layout="wide")
st.title("📊 Radar de Vagas: SP e Remotas")
st.markdown("Monitoramento de IA para vagas de tecnologia de alta qualidade.")

try:
    with open('vagas.json', 'r', encoding='utf-8') as f:
        vagas = json.load(f)
except FileNotFoundError:
    st.error("Arquivo de dados não encontrado.")
    st.stop()

if not vagas:
    st.warning("O banco de dados está vazio. O robô em breve adicionará novas vagas.")
    st.stop()

# ================= FILTROS LATERAIS =================
st.sidebar.header("Filtros")

cargos = list(set([v['categoria'] for v in vagas]))
cargo_selecionado = st.sidebar.selectbox("Filtre por Profissão:", ["Todos"] + cargos)

modelos = list(set([v.get('modelo_trabalho', 'Não mencionado') for v in vagas]))
modelo_selecionado = st.sidebar.selectbox("Modelo de Trabalho:", ["Todos"] + modelos)

# Aplicando os filtros
vagas_filtradas = vagas
if cargo_selecionado != "Todos":
    vagas_filtradas = [v for v in vagas_filtradas if v['categoria'] == cargo_selecionado]
if modelo_selecionado != "Todos":
    vagas_filtradas = [v for v in vagas_filtradas if v.get('modelo_trabalho', 'Não mencionado') == modelo_selecionado]

# ================= MÉTRICAS =================
hoje = datetime.now().strftime('%Y-%m-%d')
total_historico = len(vagas_filtradas)
vagas_hoje = len([v for v in vagas_filtradas if v.get('data_coleta') == hoje])
vagas_remotas = len([v for v in vagas_filtradas if v.get('modelo_trabalho') == 'Remoto'])

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Total de Vagas Válidas", total_historico)
col_m2.metric("Vagas Novas Hoje", vagas_hoje)
col_m3.metric("Vagas 100% Remotas", vagas_remotas)

st.markdown("---")

if not vagas_filtradas:
    st.info("Nenhuma vaga encontrada com estes filtros.")
    st.stop()

# ================= PROCESSAMENTO DOS GRÁFICOS =================
hard_skills = []
ingles_status = []
modelo_status = []

for v in vagas_filtradas:
    hard_skills.extend(v.get('hard_skills', []))
    ingles_status.append(v.get('ingles', 'Não mencionado'))
    modelo_status.append(v.get('modelo_trabalho', 'Não mencionado'))

top_hard = Counter(hard_skills).most_common(15)

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.subheader("💻 Top 15 Hard Skills")
    if top_hard:
        df_hard = pd.DataFrame(top_hard, columns=["Skill", "Menções"])
        fig_hard = px.bar(df_hard, x="Menções", y="Skill", orientation='h', color_discrete_sequence=['#00b4d8'])
        fig_hard.update_yaxes(categoryorder="total ascending")
        st.plotly_chart(fig_hard, use_container_width=True)

with col2:
    st.subheader("🏢 Modelo de Trabalho")
    if modelo_status:
        df_modelo = pd.DataFrame(modelo_status, columns=["Modelo"]).value_counts().reset_index()
        df_modelo.columns = ['Modelo', 'Quantidade']
        cores_modelo = {'Remoto': '#2a9d8f', 'Híbrido': '#e9c46a', 'Presencial': '#e76f51', 'Não mencionado': '#8d99ae'}
        fig_modelo = px.pie(df_modelo, values='Quantidade', names='Modelo', hole=0.4, color='Modelo', color_discrete_map=cores_modelo)
        st.plotly_chart(fig_modelo, use_container_width=True)

with col3:
    st.subheader("🌎 Exigência de Inglês")
    if ingles_status:
        df_ingles = pd.DataFrame(ingles_status, columns=["Nível"]).value_counts().reset_index()
        df_ingles.columns = ['Nível', 'Quantidade']
        cores_ingles = {'Obrigatório': '#d62828', 'Desejável': '#f77f00', 'Não mencionado': '#8d99ae'}
        fig_ingles = px.pie(df_ingles, values='Quantidade', names='Nível', hole=0.4, color='Nível', color_discrete_map=cores_ingles)
        fig_ingles.update_layout(showlegend=False)
        st.plotly_chart(fig_ingles, use_container_width=True)

# ================= LISTA DE VAGAS RECENTES =================
st.markdown("---")
st.subheader("📝 Últimas Vagas (Sem repetições ou vazias)")

vagas_ordenadas = sorted(vagas_filtradas, key=lambda x: x.get('data_coleta', ''), reverse=True)[:20]

for v in vagas_ordenadas:
    modelo_badge = f"🏢 {v.get('modelo_trabalho', 'N/A')}"
    with st.expander(f"{v['data_coleta']} | {v['titulo']} - {v['empresa']} | {modelo_badge}"):
        st.write(f"**🔗 Link:** [Acessar vaga no LinkedIn]({v['url']})")
        st.write(f"**🛠️ Hard Skills:** {', '.join(v.get('hard_skills', []))}")
        st.write(f"**🌎 Inglês:** {v.get('ingles', 'Não mencionado')} | **🏢 Modelo:** {v.get('modelo_trabalho', 'Não mencionado')}")
