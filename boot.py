import sqlite3
import requests
import os
import base64
from flask import Flask, request, jsonify
from datetime import datetime
import random
from datetime import datetime, date
app = Flask(__name__)

def verificar_usuario(numero_telefone):
    try:
        numero_limpo = ''.join(c for c in str(numero_telefone).split('@')[0] if c.isdigit())
        
        with sqlite3.connect('usuarios.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT numero_de_telefone, horarios, concursos,
                       questoes_ja_processadas, rascunhos_gerados
                FROM usuario
                WHERE numero_de_telefone = ?
            ''', (numero_limpo,))
            usuario = cursor.fetchone()
            
            return usuario if usuario else None

    except sqlite3.Error as e:
        print(f"!!! Erro de banco de dados ao verificar usuário: {e}")
        return None



def verificar_status_pagamento(numero_usuario):
    
    try:
        # 1. Limpeza do número para garantir compatibilidade com o banco
        numero_limpo = ''.join(c for c in str(numero_usuario).split('@')[0] if c.isdigit())

        # 2. Consulta ao Banco de Dados
        with sqlite3.connect('usuarios.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT proximo_pagamento 
                FROM usuario 
                WHERE numero_de_telefone = ?
            ''', (numero_limpo,))
            
            resultado = cursor.fetchone()

        # 3. Verificação de existência do usuário
        if not resultado:
            return False, "⚠️ Usuário não encontrado no sistema."

        data_banco_str = resultado[0]
        if not data_banco_str:
            return False, "⚠️ Data de pagamento não configurada para este usuário."

        # 4. Tratamento de Datas
        data_atual = date.today()
        # Converte a string 'YYYY-MM-DD' para objeto date
        data_vencimento = datetime.strptime(data_banco_str, '%Y-%m-%d').date()

        # 5. Regras de Negócio
        if data_atual > data_vencimento:
            # Caso Vencido
            return False, f"🚫 Acesso bloqueado. Sua assinatura venceu em {data_vencimento.strftime('%d/%m/%Y')}."

        elif data_atual == data_vencimento:
            # Caso Dia do Vencimento
            print(f"⚠️ AVISO: A fatura do usuário {numero_limpo} vence hoje!")
            return True, "✅ Acesso liberado, mas atenção: sua assinatura vence hoje!"

        else:
            # Caso em Dia
            return True, "Acesso Regular"

    except ValueError:
        return False, "❌ Erro interno: Formato de data inválido no banco de dados (esperado YYYY-MM-DD)."
    except sqlite3.Error as e:
        return False, f"❌ Erro de conexão com o banco de dados: {e}"
    except Exception as e:
        return False, f"❌ Ocorreu um erro inesperado: {e}"

def comando_menu(numero_telefone):
    mensagem = (
        "📋 *Comandos Disponíveis:*\n\n"
        "*/questao* [matéria] - Solicitar uma nova questão\n"
        "*/resposta* - Ver o comentário da última questão\n"
        "*/suporte* - Falar com nossa equipe de ajuda\n\n"
        "---"
    )
    return mensagem


def comando_suporte(usuario, args):
    
    print("\n--- Processando comando /suporte ---")
    # Substitua pelo seu link de suporte real
    link_suporte = "https://wa.me/5511912345678" 
    mensagem = f"Precisa de ajuda? Fale com nosso suporte clicando no link abaixo:\n\n{link_suporte}"
    print("-> Link de suporte enviado.")
    print("-------------------------------------\n")
    return mensagem


def comando_resposta(usuario, args):
    print("\n--- Processando comando /resposta ---")
    
    if not usuario:
        print("!!! ERRO: A função 'comando_resposta' foi chamada com um usuário nulo.")
        return "⚠️ Ocorreu um erro interno. Não foi possível verificar seus dados."

    try:
        rascunho_bruto = usuario['rascunhos_gerados']
        if isinstance(rascunho_bruto, str) and rascunho_bruto.strip():
            rascunho_limpo = rascunho_bruto.strip()
            print("-> Diagnóstico: Rascunho válido encontrado.")
            try:
                with sqlite3.connect('usuarios.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE usuario SET rascunhos_gerados = NULL WHERE numero_de_telefone = ?
                    ''', (usuario['numero_de_telefone'],))
                    conn.commit()
                    print(f"-> SUCESSO: Rascunho para o usuário {usuario['numero_de_telefone']} foi limpo do banco de dados.")
            except sqlite3.Error as e:
                print(f"!!! ALERTA: Não foi possível limpar o rascunho do banco de dados para o usuário {usuario['numero_de_telefone']}. Erro: {e}")
                # Mesmo que a limpeza falhe, o usuário ainda recebe o rascunho.

            print("-------------------------------------\n")
            return f"📝 Resposta comentada:\n\n{rascunho_limpo}"
        else:
            # O dado é None, uma string vazia, só com espaços, ou não é uma string.
            if rascunho_bruto is None:
                print("-> Diagnóstico: 'rascunhos_gerados' é None.")
            elif not isinstance(rascunho_bruto, str):
                 print(f"-> Diagnóstico: 'rascunhos_gerados' não é string (tipo: {type(rascunho_bruto)}).")
            else:
                 print("-> Diagnóstico: 'rascunhos_gerados' é uma string vazia ou com apenas espaços.")
            
            print("-------------------------------------\n")
            return "❌ Você não possui questão a ser respondida, caso isso seja um erro entre  em contato com o suporte."

    except KeyError:
        # 4. Tratamento de erro estrutural: A coluna não foi encontrada na consulta.
        print("!!! ERRO CRÍTICO: A coluna 'rascunhos_gerados' não existe no objeto 'usuario'.")
        print("   Verifique a consulta SQL em 'verificar_usuario'.")
        print("-------------------------------------\n")
        return "⚠️ Ocorreu um erro ao buscar seus dados. A estrutura de rascunhos parece estar ausente."
        
    except Exception as e:
        # 5. Tratamento de erro genérico: Captura qualquer outra falha inesperada.
        print(f"!!! ERRO INESPERADO em 'comando_resposta': {e}")
        print("-------------------------------------\n")
        return "⚠️ Um erro inesperado aconteceu ao tentar buscar seu rascunho. Tente novamente."


def comando_questao(usuario_info, texto_da_questao):
    materia = texto_da_questao
    print("---------------------------------------------------------------------------------------\n")
    
    print(f" -> Sucesso: Informações do usuário '{usuario_info['numero_de_telefone']}' recebidas.")
    
    # Valida rascunhos pendentes
    if usuario_info['rascunhos_gerados'] and usuario_info['rascunhos_gerados'] != 'False':
        return "Erro: Você ainda não respondeu sua última questão."
    
    print(" -> Sucesso: Nenhuma questão pendente.")
    
    concurso_usuario = usuario_info['concursos']
    if not concurso_usuario:
        return "está acontecendo algum erro com seu concurso informe ao suporte"
    
    print(f" -> Sucesso: Informação do concurso obtida ('{concurso_usuario}').")

    # Navega para a pasta da matéria
    caminho_base = "questoes"
    caminho_materia = os.path.join(caminho_base, concurso_usuario, materia)
    
    if not os.path.isdir(caminho_materia):
        return f"Erro: as questões para essa disciplina '{materia}' não estão disponiveis para o concurso que você escolheu ou você escreveu algo errado."

    print(f" -> Sucesso: Diretório '{caminho_materia}' encontrado.")
        
    # Seleciona imagem aleatória
    try:
        # Pega a lista de questões já processadas pelo usuário e converte para um conjunto (set) para busca rápida
        questoes_processadas = set(usuario_info['questoes_ja_processadas'].split(',')) if usuario_info['questoes_ja_processadas'] else set()

        arquivos = os.listdir(caminho_materia)
        imagens_disponiveis = [img for img in arquivos if img.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) and img not in questoes_processadas]

        if not imagens_disponiveis:
            return f"Erro: Nenhuma imagem nova encontrada para a matéria '{materia}'. Todas as questões já foram processadas."

        imagem_selecionada = random.choice(imagens_disponiveis)
        caminho_completo_imagem = os.path.join(caminho_materia, imagem_selecionada)
        
        # --- NOVO PASSO: PREPARAR O NOME PARA BUSCA NO DB DE RESPOSTAS ---
        nome_para_busca = os.path.splitext(imagem_selecionada)[0]
        
        # Conecta ao banco de dados 'respostas.db' para buscar a resposta
        try:
            with sqlite3.connect('respostas.db') as conn_respostas:
                cursor_respostas = conn_respostas.cursor()
                cursor_respostas.execute('''
                    SELECT resposta_completa
                    FROM respostas
                    WHERE codigo = ?
                ''', (nome_para_busca,)) # Usa o nome sem extensão para a busca
                resposta = cursor_respostas.fetchone()
                
                if not resposta:
                    return "Erro: algo deu errado por favor tente novamente"
                
                resposta_completa = resposta[0]
                print(" -> Sucesso: Resposta encontrada na DB 'respostas.db'.")

        except sqlite3.Error as e:
            return f"Erro de banco de dados ao buscar a resposta: {e}"

        # Conecta ao banco de dados 'usuarios.db' para atualizar as colunas
        with sqlite3.connect('usuarios.db') as conn_usuarios:
            cursor_usuarios = conn_usuarios.cursor()
            
            # Constrói a nova lista de questões processadas
            if usuario_info['questoes_ja_processadas']:
                nova_lista_questoes = usuario_info['questoes_ja_processadas'] + f',{imagem_selecionada}'
            else:
                nova_lista_questoes = imagem_selecionada

            # Atualiza as colunas `questoes_ja_processadas` e `rascunhos_gerados`
            cursor_usuarios.execute('''
                UPDATE usuario
                SET questoes_ja_processadas = ?, rascunhos_gerados = ?
                WHERE numero_de_telefone = ?
            ''', (nova_lista_questoes, resposta_completa, usuario_info['numero_de_telefone']))
            conn_usuarios.commit()
            print(" -> Sucesso: Colunas 'questoes_ja_processadas' e 'rascunhos_gerados' atualizadas.")

        print(f" -> Sucesso: Imagem selecionada: {imagem_selecionada}")
        return caminho_completo_imagem

    except Exception as e:
        return f"Erro: Ocorreu um erro ao selecionar a imagem: {e}"
    
    print("-----------------------------------------------------------------------------\n")


def enviar_imagem(caminho_imagem, numero_telefone):
    numero_destinatario = str(numero_telefone).split('@')[0]
    API_KEY = "carloscadu123"
    base64_image_data = None

    try:
        if not os.path.exists(caminho_imagem):
            return None
        
        with open(caminho_imagem, "rb") as image_file:
            base64_image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
    except Exception:
        return None
    
    if base64_image_data is None:
        return None 
    
    extensao = os.path.splitext(caminho_imagem)[1].lstrip('.')
    mime_type = f"image/{extensao}"
    nome_arquivo = os.path.basename(caminho_imagem)
    
    url = "http://evolution-api-carlos.australiaeast.cloudapp.azure.com:8081/message/sendMedia/bot_em_produçao"

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
        
        if response.status_code in [200, 201]:
            print(f"✅ SUCESSO! Status: {response.status_code}")
            return response.json()
        else:
            print(f"\n🚨 Envio falhou. Status: {response.status_code} - Resposta: {response.text}")
            return None
                
    except requests.exceptions.RequestException:
        return None

def enviar_texto(numero_telefone, texto):
    numero_destinatario = str(numero_telefone).split('@')[0]
    print(f"\n📶 Mensagem recebida desse numero: {numero_destinatario}\n")

    API_URL = "http://evolution-api-carlos.australiaeast.cloudapp.azure.com:8081/message/sendText/bot_em_produçao" # URL da sua instância
    API_KEY = "carloscadu123"                                     # Sua chave API

    # Estrutura do payload e headers
    payload = {
        "number": numero_destinatario,
        "text": texto,
        "delay": 1200, # Atraso para simular o comportamento humano
        "linkPreview": False
    }

    headers = {
        "apikey": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        # requests.post com 'json=payload' cuida da serialização e do Content-Type
        response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        
        # Levanta uma exceção para códigos de status 4xx ou 5xx
        response.raise_for_status() 

        # Se for sucesso (200, 201, etc.), retorna o JSON da resposta
        print(f"📩 Mensagem para {numero_destinatario} enviada com sucesso! mensagem:\n {texto}\n")
        

    except requests.exceptions.RequestException as e:
        # Captura erros de conexão ou erros HTTP (4xx/5xx)
        print(f"❌ Erro ao enviar mensagem para {numero_destinatario}: {e}")
        # Tenta imprimir a resposta de erro para diagnóstico, se disponível
        if 'response' in locals() and response is not None:
             print(f"Status Code de Erro: {response.status_code}")
             print(f"Corpo da Resposta de Erro: {response.text}")


'''================================= parte 2 do codigo ==============================='''
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        data = request.json
        # Ignora eventos que não sejam mensagens ou mensagens enviadas pelo próprio bot
        if not data or data.get('event') != 'messages.upsert':
            return jsonify({"status": "ignored"}), 200

        mensagem_data = data.get('data', {})
        if mensagem_data.get('key', {}).get('fromMe', False):
            return jsonify({"status": "ignored_self_message"}), 200

        texto_mensagem = mensagem_data.get('message', {}).get('conversation', '').strip()
        numero_telefone = mensagem_data.get('key', {}).get('remoteJidAlt')

        if not numero_telefone:
            return jsonify({"status": "error", "message": "Número não encontrado"}), 400

        # 1. Verifica se o usuário está cadastrado
        usuario = verificar_usuario(numero_telefone)
        if usuario is None:
            mensagem_erro = "🚫 Você não tem permissão para usar este bot. Por favor, entre em contato com o administrador."
            numero_telefone_limpo = ''.join(c for c in str(numero_telefone).split('@')[0] if c.isdigit())
            enviar_texto(numero_telefone_limpo, mensagem_erro)
            return jsonify({"status": "forbidden"}), 403

        # 2. Verifica o status do pagamento (Nova Lógica Integrada)
        status_pagamento, mensagem_pgto = verificar_status_pagamento(numero_telefone)
        
        if not status_pagamento:
            # Caso o pagamento esteja vencido ou haja erro na data
            enviar_texto(numero_telefone, mensagem_pgto)
            return jsonify({"status": "payment_required"}), 200 # Retorna 200 para o webhook não tentar reenviar

        # Se o pagamento vence hoje, envia o alerta, mas NÃO interrompe o fluxo
        if "vence hoje" in mensagem_pgto:
            enviar_texto(numero_telefone, mensagem_pgto)

        # 3. Processamento de Comandos
        if texto_mensagem.startswith('/'):
            partes = texto_mensagem.split()
            comando = partes[0].lower()
            args = partes[1:]

            if comando == "/menu":
                resposta = comando_menu(numero_telefone)
                enviar_texto(numero_telefone, resposta)

            elif comando == "/resposta":
                resposta = comando_resposta(usuario, args)
                enviar_texto(numero_telefone, resposta)

            elif comando == "/suporte":
                resposta = comando_suporte(usuario, args)
                enviar_texto(numero_telefone, resposta)

            elif comando == "/questao":
                if not args:
                    enviar_texto(numero_telefone, "⚠️ Por favor, informe a matéria. Ex: /questao constitucional")
                else:
                    texto_da_questao = ' '.join(args)
                    retorno = comando_questao(usuario, texto_da_questao)
                    
                    if isinstance(retorno, str) and retorno.lower().endswith(('.png', '.jpg', '.jpeg')):
                        enviar_imagem(retorno, numero_telefone)
                    else:
                        enviar_texto(numero_telefone, retorno)
            else:
                enviar_texto(numero_telefone, f"Comando '{comando}' não reconhecido. Digite /menu para ver as opções.")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Erro CRÍTICO ao processar o webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Na Azure, não usamos Ngrok. Usamos a porta aberta no Firewall (NSG).
    # Certifique-se de que a porta 5000 está aberta no NSG da Azure igual fizemos com a 8081.
    port = 5000
    print("=" * 70)
    print(f"* Servidor Flask INICIADO na porta {port}")
    print(f"* URL para o Webhook na Evolution API:")
    print(f"  http://evolution-api-carlos.australiaeast.cloudapp.azure.com:{port}/webhook")
    print("=" * 70)
    
    # host='0.0.0.0' permite que a Azure receba tráfego externo
    app.run(host='0.0.0.0', port=port, use_reloader=False)