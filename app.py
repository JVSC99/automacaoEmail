import email
from email.mime.text import MIMEText
import smtplib
from flask import Flask, request, jsonify
import imaplib
import os
from datetime import datetime, timedelta

app = Flask(__name__)

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
            
            # Extraindo informações do e-mail
            sender = msg.get('From')
            subject = msg.get('Subject')
            
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
            
            # Extraindo informações do e-mail
            sender = msg.get('From')
            subject = msg.get('Subject')
            
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
