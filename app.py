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
        last_id = data.get('last_id', None)
        
        # Conectar ao servidor IMAP
        objCon = imaplib.IMAP4_SSL(imap_host)
        objCon.login(login, password)
        objCon.select(mailbox='inbox', readonly=True)

        # Ler emails a partir do último id
        status, email_ids = objCon.search(None, 'ALL')
        email_ids = email_ids[0].split()

        # Verificar e-mails a partir do último lido
        if last_id:
            email_ids = [email_id for email_id in email_ids if int(email_id) > int(last_id)]
        
        emails = []
        for email_id in email_ids:
            status, data = objCon.fetch(email_id, '(RFC822)')
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            
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
                "texto": body
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

        # Conectar ao servidor IMAP
        objCon = imaplib.IMAP4_SSL(imap_host)
        objCon.login(login, password)
        objCon.select(mailbox='inbox', readonly=True)

        # Calcula a data de 7 dias atrás
        date_7_days_ago = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")

        # Buscar emails dos últimos 7 dias
        status, email_ids = objCon.search(None, f'SINCE {date_7_days_ago}')
        email_ids = email_ids[0].split()

        emails = []
        for email_id in email_ids:
            status, data = objCon.fetch(email_id, '(RFC822)')
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
            
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
                "texto": body
            })
        
        objCon.logout()
        return jsonify(emails)
    
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)

