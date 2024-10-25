import email
from email.mime.text import MIMEText
import smtplib
from flask import Flask, request, jsonify
import imaplib
import os
from email.header import decode_header
from datetime import datetime, timedelta


app = Flask(__name__)

# Função para decodificar os cabeçalhos que podem estar em UTF-8 ou outra codificação
def decode_mime_words(s):
    decoded_fragments = decode_header(s)
    return ''.join([
        fragment.decode(encoding if encoding else 'utf-8') if isinstance(fragment, bytes) else fragment
        for fragment, encoding in decoded_fragments
    ])

@app.route('/read_emails', methods=['POST'])
def read_emails():
    try:
        # Receber os dados via JSON
        data = request.get_json()
        imap_host = data.get('imap')
        login = data.get('login')
        password = data.get('password')
        
        # Receber as datas diretamente no formato ISO 8601 (ex: "2024-10-10T19:21:52+00:00")
        iso_datetime_str = data.get('iso_datetime')  # Data no formato ISO 8601
        imap_date = data.get('imap_date')  # Data no formato IMAP (ex: "20-Oct-2024")

        # Converter a string ISO 8601 para um objeto datetime "aware" (com fuso horário)
        last_datetime = datetime.fromisoformat(iso_datetime_str)

        # Conectar ao servidor IMAP
        objCon = imaplib.IMAP4_SSL(imap_host)
        objCon.login(login, password)
        objCon.select(mailbox='inbox', readonly=True)

        # Sempre buscar e-mails a partir da data no formato IMAP
        status, email_ids = objCon.search(None, f'SINCE {imap_date}')
        email_ids = email_ids[0].split()

        emails = []
        for email_id in email_ids:
            status, data = objCon.fetch(email_id, '(RFC822)')
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Extrair a data de envio do e-mail
            email_date_str = msg.get('Date')
            email_datetime = email.utils.parsedate_to_datetime(email_date_str)  # Conversão automática de data

            # Filtrar por horário (após a data e hora fornecida, ambos são "aware")
            if email_datetime <= last_datetime:
                continue  # Ignorar e-mails anteriores ao horário fornecido

            # Extraindo o remetente e o título
            sender = decode_mime_words(msg.get('From'))
            subject = decode_mime_words(msg.get('Subject'))

            # Verificar se o e-mail tem partes (multipart)
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()  # O corpo do e-mail
            else:
                body = msg.get_payload(decode=True).decode()

            # Adicionar ao JSON
            emails.append({
                "id": email_id.decode(),
                "enviado_por": sender,
                "titulo": subject,
                "texto": body,
                "data": email_datetime.strftime('%Y-%m-%d %H:%M:%S')  # Incluir a data e hora do e-mail
            })
        
        objCon.logout()
        return jsonify(emails)

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/read_emails_last_7_days', methods=['POST'])
def read_emails_last_7_days():
    try:
        # Receber os dados via JSON
        data = request.get_json()
        imap_host = data.get('imap')
        login = data.get('login')
        password = data.get('password')
        use_uid = data.get('use_uid', True)  # Padrão é True

        print(f"Tentando conectar ao servidor IMAP {imap_host} com o usuário {login}")

        # Conectar ao servidor IMAP
        objCon = imaplib.IMAP4_SSL(imap_host)
        objCon.login(login, password)
        print("Login bem-sucedido")

        objCon.select(mailbox='inbox', readonly=True)
        print("Caixa de entrada selecionada")

        # Calcular a data de 7 dias atrás
        date_since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
        print(f"Buscando e-mails desde {date_since}")

        # Buscar IDs dos e-mails desde essa data
        if use_uid:
            status, email_ids = objCon.uid('search', None, f'SINCE {date_since}')
        else:
            status, email_ids = objCon.search(None, f'SINCE {date_since}')

        email_ids = email_ids[0].split()

        print(f"Número de e-mails encontrados: {len(email_ids)}")

        emails = []
        for email_id in email_ids:
            if use_uid:
                status, data = objCon.uid('fetch', email_id, '(RFC822)')
            else:
                status, data = objCon.fetch(email_id, '(RFC822)')

            if status != 'OK':
                print(f"Erro ao buscar o e-mail ID {email_id.decode()}")
                continue

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Função auxiliar para obter o charset
            def get_charset(message, default='utf-8'):
                charset = message.get_content_charset()
                if charset is None:
                    charset = default
                return charset

            # Extraindo o remetente e o título
            sender = decode_mime_words(msg.get('From'))
            subject = decode_mime_words(msg.get('Subject'))

            # Verificar se o e-mail tem partes (multipart)
            if msg.is_multipart():
                body = ''
                for part in msg.walk():
                    if part.get_content_type() == "text/plain" and not part.is_multipart():
                        charset = get_charset(part)
                        payload = part.get_payload(decode=True)
                        if payload is None:
                            continue
                        try:
                            body += payload.decode(charset, errors='replace')
                        except (LookupError, UnicodeDecodeError):
                            # Tentar com 'latin1' se o charset não funcionar
                            body += payload.decode('latin1', errors='replace')
            else:
                charset = get_charset(msg)
                payload = msg.get_payload(decode=True)
                if payload is not None:
                    try:
                        body = payload.decode(charset, errors='replace')
                    except (LookupError, UnicodeDecodeError):
                        body = payload.decode('latin1', errors='replace')
                else:
                    body = ''

            # Adicionar ao JSON
            emails.append({
                "id": email_id.decode(),
                "enviado_por": sender,
                "titulo": subject,
                "texto": body
            })

        objCon.logout()
        print(emails)
        return jsonify(emails)

    except Exception as e:
        print( str(e))
        return jsonify({'error': str(e)})

@app.route('/send_email', methods=['POST'])
def send_email():
    try:
        # Receber os dados via JSON
        data = request.get_json()
        smtp_host = data.get('smtp_host')
        smtp_port = data.get('smtp_port')
        login = data.get('login')
        password = data.get('password')
        titulo = data.get('titulo')
        texto = data.get('texto')
        destinatario = data.get('destinatario')
        
        # Preparar o e-mail
        msg = MIMEText(texto)
        msg['Subject'] = titulo
        msg['From'] = login
        msg['To'] = destinatario

        # Verificar se a porta é 465 (SSL/TLS) ou 587 (STARTTLS)
        if smtp_port == 465:
            # Conectar usando SSL/TLS
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(login, password)
                server.sendmail(login, destinatario, msg.as_string())
        elif smtp_port == 587:
            # Conectar usando STARTTLS
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()  # Inicia o modo TLS
                server.ehlo()
                server.login(login, password)
                server.sendmail(login, destinatario, msg.as_string())
        else:
            return jsonify({"error": "Porta SMTP não suportada"}), 400
        
        return jsonify({"message": "E-mail enviado com sucesso!"})
    
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/reply_email', methods=['POST'])
def reply_email():
    try:
        # Receber os dados via JSON
        data = request.get_json()
        smtp_host = data.get('smtp_host')
        smtp_port = data.get('smtp_port')
        login = data.get('login')
        password = data.get('password')
        titulo = data.get('titulo')
        texto = data.get('texto')
        destinatario = data.get('destinatario')
        in_reply_to = data.get('in_reply_to')  # ID da mensagem original para In-Reply-To

        # Preparar o e-mail de resposta
        msg = MIMEText(texto)
        msg['Subject'] = f"Re: {titulo}"
        msg['From'] = login
        msg['To'] = destinatario
        msg['In-Reply-To'] = in_reply_to  # Definir a mensagem à qual estamos respondendo
        msg['References'] = in_reply_to  # Referenciar a mensagem original

        # Conectar ao servidor SMTP
        if smtp_port == 465:
            # Conectar usando SSL/TLS
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(login, password)
                server.sendmail(login, destinatario, msg.as_string())
        elif smtp_port == 587:
            # Conectar usando STARTTLS
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(login, password)
                server.sendmail(login, destinatario, msg.as_string())
        else:
            return jsonify({"error": "Porta SMTP não suportada"}), 400
        
        return jsonify({"message": "E-mail de resposta enviado com sucesso!"})
    
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)

