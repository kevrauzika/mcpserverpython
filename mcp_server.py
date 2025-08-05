import psycopg2 as pg
from fastapi import FastAPI,Request
import os
from dotenv import load_dotenv
import openai

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")



app = FastAPI()

def conectar():
    return pg.connect(
        dbname='postgres',
        user='postgres',
        password='khs050603',
        host='localhost',
        port='5432'
    )
    
def extrair_estrutura_banco():
    conn = conectar()
    cur = conn.cursor()
    query = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
        """
    cur.execute(query)
    rows =  cur.fetchall()
    cur.close()
    conn.close()
    
    estrutura_tabelas = {}
    for tabela , coluna, tipo in rows:
        if tabela not in estrutura_tabelas:
            estrutura_tabelas[tabela] = []
        estrutura_tabelas[tabela].append(f'{coluna} ({tipo})')
    estrutura_formatada = ''
    for tabela, coluna in estrutura_tabelas.items():
         estrutura_formatada += f"Tabela {tabela}:\n  - " + "\n  - ".join(coluna) + "\n\n"
    return estrutura_formatada
        
    
    
@app.post('/mcp')
async def mcp_endpoint(request: Request):
    body = await request.json()
    
    mensagem_id = body.get('id')
    usuario = body.get('role')
    pergunta = body.get('content').lower()

    if usuario != 'usuario':
        return {
            'id': mensagem_id,
            'role': 'assistente',
            'content': 'apenas mensagens do tipo usuarios sao aceitas'
        }


    nome = extrair_nome(pergunta)

    if not nome:
        estrutura = extrair_estrutura_banco()
        sql = gerar_sql_llm(pergunta, estrutura)
        colunas, dados =  executar_sql(sql)
        
        print("SQL gerada:", sql)
        print("Colunas:", colunas)
        print("Dados:", dados)
        
        if isinstance(dados, str):
            resposta_final = dados
        else:
             prompt_resposta = (
                f"O usuário perguntou: \"{pergunta}\"\n\n"
                f"A seguinte SQL foi executada:\n{sql}\n\n"
                f"E retornou os seguintes dados:\n{colunas}\n{dados}\n\n"
                f"Com base nisso, gere uma resposta clara e educada."
            )
             
             resposta_final = openai.ChatCompletion.create(
                 model="gpt-3.5-turbo",
                 messages=[{ "role": "user", "content": prompt_resposta }],
                 temperature=0.5,
                 max_tokens=300
             ).choices[0].message.content
        return{
            'id': mensagem_id,
            'role': 'assistente',
            'content': resposta_final
        }
    cliente = buscar_cliente_nome(nome)
    if cliente:
        resposta_llm = gerar_resposta_llm(pergunta, cliente)
        return{
            'id': mensagem_id,
            'role': 'assistente',
            'content': resposta_llm
        }
    resposta_llm = gerar_resposta_llm(pergunta)
    return {
        'id': mensagem_id,
        'role': 'assistente',
        'content': resposta_llm
    }

def extrair_nome(pergunta):
    palavras = pergunta.split()
    for i in range(len(palavras)-1):
        if palavras[i] == 'de' or palavras[i] == 'da':
            return palavras[i+1].capitalize()
    return None

def buscar_cliente_nome(nome):
    conn = conectar()
    cur = conn.cursor()
    query = 'SELECT "Nome", "Situacao" FROM "Clientes" WHERE "Nome" ILIKE %s LIMIT 1'

    cur.execute(query,(f'%{nome}%',))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {'nome': row[0], 'situacao': row[1]}
    return None

def gerar_sql_llm(pergunta: str, estrutura_banco: str) -> str:
    prompt = (
        f"Você é um assistente técnico com acesso ao seguinte schema PostgreSQL:\n\n"
        f"{estrutura_banco.lower()}\n\n"
        f"A pergunta do usuário é:\n\"{pergunta}\"\n\n"
        f"Com base nisso, gere apenas a consulta SQL que deve ser executada no banco, "
        f"usando **nomes de tabelas e colunas todos em minúsculo e sem aspas**, "
        f"e trate os valores textuais com `ILIKE` para ignorar maiúsculas e minúsculas. "
        f"Retorne apenas a SQL entre três crases (```sql ... ```), nada mais."
        f"... gere a SQL considerando que a coluna situacao contém valores como 'Ativo', 'Inativo' e 'Pendente'."
    )

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=200,
    )

    texto = response.choices[0].message.content

    if "```sql" in texto:
        return texto.split("```sql")[1].split("```")[0].strip()
    return texto.strip()

def executar_sql(sql:str):
    conn = conectar()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        resultado = cur.fetchall()
        colunas = [desc[0] for desc in cur.description]
    except Exception as e:
        resultado = f'erro ao executar consulta: {e}'
        colunas = []
    cur.close()
    conn.close()
    return colunas, resultado

def gerar_resposta_llm(pergunta, cliente=None):
    estrutura_banco = extrair_estrutura_banco()
    if cliente: 
        nome = cliente['nome']
        situacao = cliente['situacao']
        prompt = (
            f'O usuário perguntou: {pergunta}. '
            f'O nome do cliente é {nome} e a situação é {situacao}. '
            f'Responda de forma educada e clara.'
        )
    else:
        prompt = (
            f"O usuário perguntou: {pergunta}. "
            f"Utilize o schema do banco para entender e gerar uma resposta, mesmo que o nome do cliente não esteja presente."
        )

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                   "Você é um assistente virtual com acesso ao seguinte schema de banco de dados PostgreSQL:\n\n"
                    f"{estrutura_banco}\n"
                    "Quando possível, gere uma consulta SQL baseada na pergunta do usuário, execute no banco de dados e retorne o resultado de forma educada e clara."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7,
        max_tokens=150
    )
    return response.choices[0].message.content
