from flask import Flask, request, jsonify
import imaplib
import os

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
            emails.append({'id': email_id.decode(), 'data': data[0][1].decode()})
        
        objCon.logout()
        return jsonify(emails)
    
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Pega a porta da variável de ambiente
    app.run(host='0.0.0.0', port=port)  # Usa a porta dinâmica

