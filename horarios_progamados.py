import sqlite3
import pytz
import time
import os
import random 
import base64
import requests
from datetime import datetime, date


def verificar_horarios():
    try:
        # Configura o fuso horário brasileiro
        tz = pytz.timezone('America/Sao_Paulo')
        
        # Obtém a hora atual no fuso horário brasileiro
        agora = datetime.now(tz)
        hora_atual = agora.strftime('%H:%M')
        
        # Conecta ao banco de dados
        with sqlite3.connect('usuarios.db') as conn:
            cursor = conn.cursor()
            
            # Busca todos os usuários e seus horários
            cursor.execute("SELECT numero_de_telefone, horarios FROM usuario")
            usuarios_e_horarios = cursor.fetchall()
            
            usuarios_para_processar = []
            
            # Itera sobre cada usuário para verificar seus horários
            for numero_de_telefone, horarios_str in usuarios_e_horarios:
                if horarios_str:  # Garante que a string de horários não está vazia
                    horarios = [h.strip() for h in horarios_str.split(',')]
                    if hora_atual in horarios:
                        usuarios_para_processar.append(numero_de_telefone)
            
            if usuarios_para_processar:
                print(f"[{agora}] Encontrados {len(usuarios_para_processar)} usuários para processamento")
                return usuarios_para_processar
            else:
                print(f"[{agora}] Escaneando database...")
                print(f"[{agora}] Nenhum horário foi encontrado.")
                return []
        
    except sqlite3.Error as e:
        print(f"[{datetime.now()}] Erro ao acessar banco de dados: {str(e)}")
        return []
    except Exception as e:
        print(f"[{datetime.now()}] Erro inesperado: {str(e)}")
        return []


def processar_questoes(numero_usuario):
    try:
        with sqlite3.connect('usuarios.db') as conn_usuarios:
            cursor_usuarios = conn_usuarios.cursor()
            
            # Consulta as informações do usuário
            cursor_usuarios.execute("""
                SELECT rascunhos_gerados, questoes_ja_processadas, concursos, proximo_pagamento
                FROM usuario
                WHERE numero_de_telefone = ?
            """, (numero_usuario,))
            
            usuario_info = cursor_usuarios.fetchone()
            
            if usuario_info is None:
                return "algo não ocorreu como esperado informe ao suporte"
                
            usuario_info = {
                'rascunhos_gerados': usuario_info[0],
                'questoes_ja_processadas': usuario_info[1],
                'concursos': usuario_info[2],
                'proximo_pagamento': usuario_info[3]
            }

        data_pagamento_str = usuario_info.get('proximo_pagamento')
        
        if data_pagamento_str:
            try:
                hoje = date.today()
                # Converte a string YYYY-MM-DD em um objeto date
                data_pagamento = datetime.strptime(data_pagamento_str, '%Y-%m-%d').date()

                print(f" -> Verificação de Pagamento: Hoje é {hoje}, Próximo Pagamento é {data_pagamento}.")

                if hoje > data_pagamento:
                    # CASO 1: A data de pagamento VENCEU
                    print(" -> Acesso Negado: Pagamento Atrasado.")
                    return "Acesso Bloqueado: você não atualizou o pagamento"
                
                elif hoje == data_pagamento:
                    # CASO 2: A data de pagamento é HOJE
                    texto_aviso = f"Atenção, o seu pagamento vence hoje, {data_pagamento_str}, pague antes do vencimento para evitar bloqueio."
                    falha_envio(texto_aviso, numero_usuario) 
                    print(" -> Sucesso: Aviso de pagamento enviado. Continuando o processamento.")
                    
            except ValueError:
                print(f" -> ERRO: Formato de data inválido ('{data_pagamento_str}') na DB. Seguindo com o processamento.")
        

        # Valida rascunhos pendentes
        if usuario_info['rascunhos_gerados'] and usuario_info['rascunhos_gerados'] != 'False':
            return "Erro: Você ainda não respondeu sua última questão, e por isso sua questão agendada para agora não foi enviada."

        concurso_usuario = usuario_info['concursos']
        
        if not concurso_usuario:
            return "está acontecendo algum erro com seu concurso informe ao suporte"
        
        print(f" -> Sucesso: Informação do concurso obtida ('{concurso_usuario}').")
        
        # Navega para a pasta do concurso
        caminho_base = "questoes"
        caminho_concurso = os.path.join(caminho_base, concurso_usuario)
        
        if not os.path.isdir(caminho_concurso):
            return f"765 Erro: O diretório para o concurso '{concurso_usuario}' não foi encontrado."
            
        materias_disponiveis = [d for d in os.listdir(caminho_concurso) if os.path.isdir(os.path.join(caminho_concurso, d))]
        
        if not materias_disponiveis:
            return " 423 Erro: algo não ocorreu como esperado informe ao suporte."
            
        materia_selecionada = random.choice(materias_disponiveis)
        print(f" -> Sucesso: Matéria '{materia_selecionada}' selecionada aleatoriamente.")
        
        caminho_materia = os.path.join(caminho_concurso, materia_selecionada)
        
        try:
            questoes_processadas = set(usuario_info['questoes_ja_processadas'].split(',')) if usuario_info['questoes_ja_processadas'] else set()
            
            arquivos = os.listdir(caminho_materia)
            imagens_disponiveis = [
                img for img in arquivos 
                if img.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) 
                and img not in questoes_processadas
            ]
            
            if not imagens_disponiveis:
                return f"424 Erro: algo não ocorreu como esperado informe ao suporte."
            
            imagem_selecionada = random.choice(imagens_disponiveis)
            caminho_completo_imagem = os.path.join(caminho_materia, imagem_selecionada)
            nome_para_busca = os.path.splitext(imagem_selecionada)[0]
            
            try:
                with sqlite3.connect('respostas.db') as conn_respostas:
                    cursor_respostas = conn_respostas.cursor()
                    
                    cursor_respostas.execute("""
                        SELECT resposta_completa 
                        FROM respostas 
                        WHERE codigo = ?
                    """, (nome_para_busca,))
                    
                    resposta = cursor_respostas.fetchone()
                    
                    if not resposta:
                        return "005 Erro: algo não ocorreu como esperado informe ao suporte."
                    
                    resposta_completa = resposta[0]
                    print(" -> Sucesso: Resposta encontrada na DB 'respostas.db'.")
                    
            except sqlite3.Error as e:
                return "006 Erro: algo não ocorreu como esperado informe ao suporte."
            
            # Atualiza colunas no banco usuarios.db
            with sqlite3.connect('usuarios.db') as conn_usuarios:
                cursor_usuarios = conn_usuarios.cursor()
                
                if usuario_info['questoes_ja_processadas']:
                    nova_lista_questoes = usuario_info['questoes_ja_processadas'] + f',{imagem_selecionada}'
                else:
                    nova_lista_questoes = imagem_selecionada
                
                cursor_usuarios.execute("""
                    UPDATE usuario 
                    SET questoes_ja_processadas = ?, rascunhos_gerados = ?
                    WHERE numero_de_telefone = ?
                """, (nova_lista_questoes, resposta_completa, numero_usuario))
                
                conn_usuarios.commit()
                print(" -> Sucesso: Colunas 'questoes_ja_processadas' e 'rascunhos_gerados' atualizadas.")
                print(f" -> Sucesso: Imagem selecionada: {imagem_selecionada}")
                
                return caminho_completo_imagem
            
        except Exception as e:
            return f"332 Erro: Ocorreu um erro ao selecionar a imagem: {e}"
    
    except Exception as e:
        return f"331 Erro inesperado durante o processamento: {str(e)}"
 

def sucesso_envio(caminho_imagem, numero_usuario):
    numero_destinatario = str(numero_usuario).split('@')[0]
    API_KEY = "carloscadu123"
    base64_image_data = None

    try:
        if not os.path.exists(caminho_imagem):
            print(f"❌ Erro: O arquivo não foi encontrado em: {caminho_imagem}")
            return None
        
        with open(caminho_imagem, "rb") as image_file:
            base64_image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
    except Exception as e:
        print(f"🚨 Erro ao processar o arquivo local: {str(e)}")
        return None
    
    extensao = os.path.splitext(caminho_imagem)[1].lstrip('.')
    mime_type = f"image/{extensao}"
    nome_arquivo = os.path.basename(caminho_imagem)
    
    url = "http://evolution-api-carlos.australiaeast.cloudapp.azure.com:8081/message/sendMedia/bot"

    payload = {
        "number": numero_destinatario,
        "mediatype": "image",
        "mimetype": mime_type,
        "media": base64_image_data, 
        "fileName": nome_arquivo,
        "delay": 100,
        "linkPreview": False, 
    }
    
    headers = {
        "apikey": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        
        # Verifica se o status code é de sucesso (200-299)
        response.raise_for_status() 
        
        print(f"✅ SUCESSO! Questão enviada para {numero_destinatario}")
        return response.json()

    except requests.exceptions.HTTPError as http_err:
        # Erros retornados pelo servidor (Ex: 400 Bad Request, 401 Unauthorized)
        print(f"🚨 Erro de HTTP da API: {http_err}")
        print(f"🔍 Detalhes da Resposta do Servidor: {response.text}")
    except requests.exceptions.ConnectionError:
        print("🚨 Erro de Conexão: Não foi possível conectar ao servidor (o bot está rodando?)")
    except requests.exceptions.Timeout:
        print("🚨 Erro: A requisição demorou demais (Timeout).")
    except requests.exceptions.RequestException as e:
        # Captura qualquer outro erro relacionado ao requests
        print(f"🚨 Erro inesperado na requisição: {e}")
    
    return None


def falha_envio(mensagem_erro, numero_usuario):
    numero_destinatario = str(numero_usuario).split('@')[0]
    API_URL = "http://evolution-api-carlos.australiaeast.cloudapp.azure.com:8081/message/sendText/bot" 
    API_KEY = "carloscadu123"

    payload = {
        "number": numero_destinatario,
        "text": mensagem_erro,
        "delay": 1200, 
        "linkPreview": False
    }

    headers = {
        "apikey": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status() 
        print(f"✅ Mensagem de texto enviada para {numero_destinatario}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao enviar mensagem: {e}")

def main():
    while True:
        try:
            print("--- INICIANDO PROCESSO DE BUSCA ---")
            usuarios_para_processar = verificar_horarios()
            
            for numero_usuario in usuarios_para_processar:
                resultado = processar_questoes(numero_usuario)
                
                # Verifica se o resultado é um caminho de arquivo existente
                if resultado and os.path.isfile(resultado):
                    sucesso_envio(resultado, numero_usuario)
                else:
                    falha_envio(resultado, numero_usuario)
                    print(f"❌ erro: {resultado}")
                
            time.sleep(60) 
            
        except Exception as e:
            print(f"[{datetime.now()}] Erro na função main: {str(e)}")
            time.sleep(60)

if __name__ == "__main__":
    main()