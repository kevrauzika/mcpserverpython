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
            'content': 'apenas mensagens do tipo usuarios sao aceitas'
        }


    nome = extrair_nome(pergunta)

    if not nome:
        resposta_llm = gerar_resposta_llm(pergunta)
        return {
            'id': mensagem_id,
            'role': 'assistente',
            'content': resposta_llm
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

def gerar_resposta_llm(pergunta, cliente=None):
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
            f'O usuário perguntou: {pergunta}. '
            f'Não conseguimos identificar o cliente. '
            f'Peça para ele reformular a pergunta.'
        )

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Você é um assistente virtual que ajuda a responder perguntas sobre clientes."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=150
    )
    return response.choices[0].message.content
