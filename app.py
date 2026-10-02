import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re

# Configuração para telas de celular
st.set_page_config(
    page_title="Controle Financeiro APA",
    page_icon="💳",
    layout="centered"
)

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

STATUS_LIST = ["PAGAR", "PAGO", "RECEBER", "RECEBIDO", "DIVIDENDO"]
ORIGENS = ["RICO", "NUBANK", "MP", "ITAÚ DÉBITO", "C6 BANK", "PIX", "DINHEIRO", "OUTROS", "ITAÚ CRÉDITO", "NU DÉBITO"]
CATEGORIAS = [
    "ABASTECIMENTO ZONTES", "ALIMENTAÇÃO CASA", "ALIMENTAÇÃO FAMÍLIA",
    "ALIMENTAÇÃO TRAB", "ASSINATURAS", "CASA - FIXO", "DIVERSOS",
    "EDUCAÇÃO - CURSOS", "EMPRÉSTIMO", "INFORMÁTICA - ACESSÓRIOS",
    "LAZER COM AMIGOS", "LAZER COM FAMÍLIA", "MAYA", "MERCADO", "PRESENTES",
    "SAÚDE", "SEGURO", "TRANSPORTE", "TRANSPORTE - APLICATIVOS E TAXI",
    "UTILIDADES CASA", "VESTUÁRIO", "VIAGENS", "OUTROS"
]
COLABORADORES = ["Eu", "Thayna", "Eu e Thayna"]

@st.cache_resource
def conectar_planilha():
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    cliente = gspread.authorize(credentials)
    return cliente.open_by_key("1YV1liuxfj8Bob6Fr1Ozjz0kPv8uiJ4G9lTA3gNlRaTs")

try:
    planilha = conectar_planilha()
except Exception as e:
    st.error(f"Erro ao conectar com a planilha: {e}")
    st.stop()

# Helper: Converte valores monetários
def converter_valor(val_str):
    if not val_str:
        return 0.0
    try:
        limpo = str(val_str).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
        return float(limpo)
    except:
        return 0.0

# Helper: Interpreta parcelas em formato Texto/Data
def ler_parcela(parc_str):
    if not parc_str:
        return None
    parc_str = str(parc_str).strip()
    match = re.search(r'(\d{1,2})[\/\-](\d{1,2})', parc_str)
    if match:
        atual = int(match.group(1))
        total = int(match.group(2))
        if 1 <= atual <= 99 and 1 <= total <= 99:
            return atual, total
    return None

# Helper: Retorna abas mensais ordenadas
def obter_abas_mensais(planilha):
    worksheets = planilha.worksheets()
    abas_mensais = []
    for w in worksheets:
        partes = w.title.split("_")
        if len(partes) == 2 and partes[0] in MESES and partes[1].isdigit():
            idx_m = MESES.index(partes[0])
            ano = int(partes[1])
            abas_mensais.append((ano * 12 + idx_m, w))
    abas_mensais.sort(key=lambda x: x[0])
    return [w for _, w in abas_mensais]

# --- NAVEGAÇÃO MOBILE ---
aba_selecionada = st.radio(
    "Navegação",
    ["➕ Lançar", "🎯 Planejamento", "📊 Dashboard", "⚖️ Rateio", "⚙️ Automações"],
    horizontal=True
)

st.divider()

# ==========================================
# 1. NOVO LANÇAMENTO
# ==========================================
if aba_selecionada == "➕ Lançar":
    st.header("💸 Novo Lançamento")
    
    with st.form("form_despesas", clear_on_submit=True):
        data = st.date_input("Data", value=datetime.today())
        descricao = st.text_input("Descrição", placeholder="Ex: Mercado Tauste, Gasolina Zontes")
        valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
        
        c1, c2 = st.columns(2)
        with c1:
            origem = st.selectbox("Origem / Cartão", ORIGENS)
        with c2:
            categoria = st.selectbox("Categoria", CATEGORIAS)
            
        c3, c4 = st.columns(2)
        with c3:
            status = st.selectbox("Status", STATUS_LIST)
        with c4:
            colaborador = st.selectbox("Colaborador", COLABORADORES)
            
        parcela = st.text_input("Parcelas", value="-", placeholder="Ex: 01/03 ou -")
        obs = st.text_input("Observações (opcional)", value="")
        
        submit = st.form_submit_button("Registrar Lançamento", use_container_width=True)
        
        if submit:
            if not descricao or valor <= 0:
                st.warning("⚠️ Preencha a descrição e um valor maior que zero.")
            else:
                try:
                    nome_aba = f"{MESES[data.month - 1]}_{data.year}"
                    try:
                        aba = planilha.worksheet(nome_aba)
                    except:
                        aba = planilha.sheet1

                    data_str = data.strftime("%d/%m/%Y")
                    nova_linha = [data_str, f"R$ {valor:.2f}", descricao, parcela, origem, categoria, status, obs, colaborador]
                    aba.append_row(nova_linha)
                    st.success(f"✅ Registrado com sucesso em **{nome_aba}**!")
                except Exception as ex:
                    st.error(f"Erro ao salvar: {ex}")

# ==========================================
# 2. PLANEJAMENTO & OBJETIVOS
# ==========================================
elif aba_selecionada == "🎯 Planejamento":
    st.header("🎯 Planejamento & Objetivos")
    
    abas_m = obter_abas_mensais(planilha)
    liberando = []
    total_liberando = 0.0
    nome_ref = "—"
    
    if abas_m:
        ultima_aba = abas_m[-1]
        nome_ref = ultima_aba.title.replace("_", " ")
        dados = ultima_aba.get_all_values()
        
        if len(dados) >= 3:
            for row in dados[2:]:
                if len(row) >= 4:
                    desc = row[2].strip()
                    val = converter_valor(row[1])
                    orig = row[4].strip() if len(row) > 4 else ""
                    parc_info = ler_parcela(row[3])
                    
                    if desc and val > 0 and parc_info:
                        atual, total = parc_info
                        if total >= 2:
                            quando = None
                            if atual == total:
                                quando = "este mês"
                            elif atual == total - 1:
                                quando = "mês que vem"
                                
                            if quando:
                                liberando.append({"desc": desc, "parc": f"{atual:02d}/{total:02d}", "valor": val, "orig": orig, "quando": quando})
                                total_liberando += val

    st.subheader(f"🔓 Parcelas Liberando ({nome_ref})")
    st.info(f"💰 Total prestes a liberar: **R$ {total_liberando:,.2f}/mês**")
    
    if liberando:
        for item in liberando:
            tag = "✅ Este mês" if item["quando"] == "este mês" else "🔜 Mês que vem"
            st.write(f"• **{item['desc']}** ({item['orig']}) - R$ {item['valor']:,.2f} | `{item['parc']}` → **{tag}**")
    else:
        st.caption("Nenhuma parcela encerrando este mês ou no próximo.")
        
    st.divider()
    st.subheader("🛒 Simulador de Objetivos")
    
    with st.form("simulador_obj"):
        item_obj = st.text_input("Item / Objetivo que deseja comprar", placeholder="Ex: TV Nova, Viagem")
        valor_obj = st.number_input("Valor Estimado (R$)", min_value=0.0, format="%.2f")
        max_parc_obj = st.number_input("Máx. Parcelas Desejadas", min_value=1, max_value=48, value=12)
        btn_simular = st.form_submit_button("Analisar Compra", use_container_width=True)
        
        if btn_simular and valor_obj > 0:
            sobra_ref = 3000.0  # Sobra média estimada
            
            if valor_obj <= sobra_ref * 0.35:
                st.success(f"✅ **PODE COMPRAR À VISTA** — representa {int((valor_obj/sobra_ref)*100)}% da sua sobra estimada.")
            elif total_liberando > 0 and (valor_obj / max_parc_obj) <= total_liberando * 1.1:
                st.info(f"🔓 **USAR PARCELAS QUE LIBERAM** — {max_parc_obj}x de R$ {valor_obj/max_parc_obj:,.2f} entra exatamente no lugar das parcelas que vão liberar (R$ {total_liberando:,.2f}/mês).")
            elif (valor_obj / max_parc_obj) / sobra_ref <= 0.30:
                st.warning(f"💳 **PARCELAR RECOMENDADO** — {max_parc_obj}x de R$ {valor_obj/max_parc_obj:,.2f} compromete {int(((valor_obj/max_parc_obj)/sobra_ref)*100)}% da sobra mensal.")
            else:
                st.error(f"⚠️ **CUIDADO — APERTAR O CINTO** — mesmo em {max_parc_obj}x (R$ {valor_obj/max_parc_obj:,.2f}/mês) compromete uma parte muito alta do orçamento.")

# ==========================================
# 3. DASHBOARD ANUAL
# ==========================================
elif aba_selecionada == "📊 Dashboard":
    st.header("📊 Dashboard Anual 2026")
    
    dash_sheet = None
    try:
        dash_sheet = planilha.worksheet("Dashboard_2026")
    except:
        try:
            dash_sheet = planilha.worksheet("Dashboard")
        except:
            pass
            
    if dash_sheet:
        dados_dash = dash_sheet.get_all_values()
        if len(dados_dash) >= 6:
            colunas = dados_dash[1][1:]  # Meses Jan-Dez
            pagos = [converter_valor(v) for v in dados_dash[2][1:]]
            recebidos = [converter_valor(v) for v in dados_dash[3][1:]]
            saldos = [converter_valor(v) for v in dados_dash[5][1:]]
            
            st.subheader("📈 Resumo Mês a Mês")
            mes_escolhido = st.selectbox("Escolha o Mês", colunas, index=datetime.today().month - 1)
            idx_m = colunas.index(mes_escolhido)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("🔴 PAGO", f"R$ {pagos[idx_m]:,.2f}")
            c2.metric("🟢 RECEBIDO", f"R$ {recebidos[idx_m]:,.2f}")
            c3.metric("💰 SALDO", f"R$ {saldos[idx_m]:,.2f}")
            
            st.divider()
            st.subheader("📋 Tabela Consolidada Anual")
            for i in range(2, len(dados_dash)):
                if dados_dash[i][0]:
                    st.write(f"**{dados_dash[i][0]}**")
                    st.caption(" | ".join([f"{colunas[j]}: {dados_dash[i][j+1]}" for j in range(len(colunas))]))
    else:
        st.info("Aba Dashboard não encontrada ou necessita atualização.")

# ==========================================
# 4. ACERTO DE CONTAS (RATEIO)
# ==========================================
elif aba_selecionada == "⚖️ Rateio":
    st.header("⚖️ Acerto de Contas (Rateio)")
    
    abas_m = obter_abas_mensais(planilha)
    if abas_m:
        nomes_abas = [w.title for w in abas_m]
        aba_sel_nome = st.selectbox("Selecione o Mês para Ratear", nomes_abas, index=len(nomes_abas)-1)
        aba_rateio = planilha.worksheet(aba_sel_nome)
        dados = aba_rateio.get_all_values()
        
        adriano_solo = 0.0
        thayna_solo = 0.0
        compartilhado = 0.0
        
        if len(dados) >= 3:
            for row in dados[2:]:
                if len(row) >= 9:
                    val = converter_valor(row[1])
                    sta = row[6].strip().upper()
                    colab = row[8].strip()
                    
                    if sta in ["PAGAR", "PAGO"] and val > 0:
                        if colab == "Eu":
                            adriano_solo += val
                        elif colab == "Thayna":
                            thayna_solo += val
                        elif colab == "Eu e Thayna":
                            compartilhado += val
                            
            cota_adriano = adriano_solo + (compartilhado / 2.0)
            cota_thayna = thayna_solo + (compartilhado / 2.0)
            
            st.subheader(f"📊 Resumo de {aba_sel_nome.replace('_', ' ')}")
            st.write(f"• **Gastos Individuais Adriano:** R$ {adriano_solo:,.2f}")
            st.write(f"• **Gastos Individuais Thayna:** R$ {thayna_solo:,.2f}")
            st.write(f"• **Gastos Compartilhados (Casal):** R$ {compartilhado:,.2f}")
            
            st.divider()
            c1, c2 = st.columns(2)
            c1.metric("👤 Cota Adriano", f"R$ {cota_adriano:,.2f}")
            c2.metric("👩 Cota Thayna", f"R$ {cota_thayna:,.2f}")
            
            st.success(f"💡 **CONCLUSÃO:** Assumindo pagamentos centralizados por você, a Thayna deve transferir para você: **R$ {cota_thayna:,.2f}**")

# ==========================================
# 5. AUTOMAÇÕES DA PLANILHA
# ==========================================
elif aba_selecionada == "⚙️ Automações":
    st.header("⚙️ Ações da Planilha")
    st.write("Execute aqui as automações equivalentes ao menu da sua planilha do Google Sheets:")
    
    # BOTÃO 1: Criar Próxima Aba Mensal
    if st.button("📋 Criar Próxima Aba Mensal", use_container_width=True):
        try:
            abas_m = obter_abas_mensais(planilha)
            if not abas_m:
                st.error("Nenhuma aba mensal encontrada.")
            else:
                ultima_aba = abas_m[-1]
                p = ultima_aba.title.split("_")
                idx_m = MESES.index(p[0])
                ano = int(p[1])
                
                prox_m_idx = (idx_m + 1) % 12
                prox_ano = ano + (1 if idx_m == 11 else 0)
                nome_proximo = f"{MESES[prox_m_idx]}_{prox_ano}"
                
                try:
                    planilha.worksheet(nome_proximo)
                    st.warning(f"A aba `{nome_proximo}` já existe!")
                except:
                    # Lê parcelas e despesas fixas para transportar
                    dados = ultima_aba.get_all_values()
                    linhas_novas = []
                    
                    if len(dados) >= 3:
                        for row in dados[2:]:
                            if len(row) >= 9 and row[2].strip():
                                desc = row[2].strip()
                                val = row[1]
                                orig = row[4]
                                cat = row[5]
                                sta = row[6].strip().upper()
                                obs = row[7]
                                colab = row[8]
                                parc_info = ler_parcela(row[3])
                                
                                deve_copiar = False
                                nova_parc = ""
                                novo_sta = "RECEBER" if sta in ["RECEBER", "RECEBIDO", "DIVIDENDO"] else "PAGAR"
                                
                                if parc_info:
                                    atual, total = parc_info
                                    if atual < total:
                                        deve_copiar = True
                                        nova_parc = f"{atual + 1:02d}/{total:02d}"
                                elif cat.strip() == "CASA - FIXO":
                                    deve_copiar = True
                                    nova_parc = "-"
                                    
                                if deve_copiar:
                                    hoje_str = datetime.today().strftime("%d/%m/%Y")
                                    linhas_novas.append([hoje_str, val, desc, nova_parc, orig, cat, novo_sta, obs, colab])
                                    
                    nova_w = planilha.duplicate_sheet(ultima_aba.id, new_sheet_name=nome_proximo)
                    # Limpa os dados antigos e insere os novos
                    nova_w.clear_contents()
                    nova_w.append_row([f"💳 CONTROLE FINANCEIRO — {nome_proximo.replace('_', ' ').upper()}"])
                    nova_w.append_row(["DATA", "VALOR", "DESCRIÇÃO", "PARC.", "ORIGEM", "CATEGORIA", "STATUS", "OBS", "COLABORADOR"])
                    for l in linhas_novas:
                        nova_w.append_row(l)
                        
                    st.success(f"✅ Aba **{nome_proximo}** criada com sucesso com {len(linhas_novas)} lançamentos continuados!")
        except Exception as ex:
            st.error(f"Erro ao criar próxima aba: {ex}")
