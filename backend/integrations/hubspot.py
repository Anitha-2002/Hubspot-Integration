#hubspot.py

import json
import secrets
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import base64
import requests
import logging
from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CLIENT_ID = '5625e450-684f-444c-ba9a-40a5da66bedb'  
CLIENT_SECRET = 'd8772e01-b078-4b53-893a-9bc1fe600f1d' 
encoded_client_id_secret = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()
SCOPES = 'crm.objects.contacts.read crm.objects.deals.read crm.objects.contacts.write oauth'
REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'
authorization_url = f'https://app.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope={SCOPES}'

async def authorize_hubspot(user_id, org_id):
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = json.dumps(state_data)
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', encoded_state, expire=3600) 
    return f'{authorization_url}&state={encoded_state}'

async def oauth2callback_hubspot(request: Request):
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error'))
    
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    
    if not code or not encoded_state:
        raise HTTPException(status_code=400, detail='Missing code or state parameter')
    
    try:
        state_data = json.loads(encoded_state)
        original_state = state_data.get('state')
        user_id = state_data.get('user_id')
        org_id = state_data.get('org_id')
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail='Invalid state parameter')
    
    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')
    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                'https://api.hubapi.com/oauth/v1/token',
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': REDIRECT_URI,
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Failed to obtain credentials: {e.response.text}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {str(e)}")
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    
    credentials = response.json()
    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(credentials), expire=3600)
    logger.info(f"Credentials stored for user {user_id} in org {org_id}")

    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)

async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        logger.error(f"No credentials found for user {user_id} in org {org_id}")
        raise HTTPException(status_code=400, detail='No credentials found.')
    return json.loads(credentials)

def create_integration_item_metadata_object(response_json: dict) -> IntegrationItem:
    return IntegrationItem(
        id=response_json.get('id'),
        type='HubSpot Object',
        name=response_json.get('properties', {}).get('firstname', '') + ' ' + response_json.get('properties', {}).get('lastname', ''),
        creation_time=response_json.get('createdAt'),
        last_modified_time=response_json.get('updatedAt'),
        parent_id=None
    )
async def get_items_hubspot(credentials) -> list[IntegrationItem]:
    """
    Fetches items from HubSpot and returns a list of IntegrationItem objects.
    """
    credentials = json.loads(credentials)
    access_token = credentials.get("access_token")
    
    if not access_token:
        raise HTTPException(status_code=400, detail="No valid access token found.")
    
    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Error fetching items from HubSpot: {response.json()}"
        )
    
    data = response.json().get("results", [])
    integration_items = []

    for item in data:
        integration_item = IntegrationItem(
            id=item.get("id"),
            type="contact",
            name=item.get("properties", {}).get("firstname", "Unnamed") + " " +
                 item.get("properties", {}).get("lastname", ""),
            creation_time=item.get("properties", {}).get("createdate"),
            last_modified_time=item.get("properties", {}).get("lastmodifieddate"),
            parent_id=None,  
        )
        integration_items.append(integration_item)
    
    return integration_items

    
