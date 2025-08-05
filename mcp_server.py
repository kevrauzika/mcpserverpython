import psycopg2 as pg
from fastapi import FastAPI,Request
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')


app = FastAPI()

def conectar():
    return pg.connect(
        dbname='postgres',
        user='postgres',
        password='khs050603',
        host='localhost',
        port='5433'
    )


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
            'content': 'esperando mensagens do tipo usuario'
        }


    nome = extrair_nome(pergunta)

    if not nome:
        return {
            'id': mensagem_id,
            'role': 'assistente',
            'content': 'Nao entendi qual cliente voce quer consultar.'
        }
    cliente = buscar_cliente_nome(nome)
    if cliente:
        return{
            'id': mensagem_id,
            'role': 'assistente',
            'content': f'O cliente {cliente["nome"]} esta {cliente["situacao"]}.'
        }
    return {
        'id': mensagem_id,
        'role': 'assistente',
        'content': f'Cliente {nome} nao encontrado.'
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

def gerar_resposta_llm(pergunta,cliente):
    nome = cliente['nome']
    situacao = cliente['situacao']

    prompt = f'o usuario perguntou: {pergunta}'
