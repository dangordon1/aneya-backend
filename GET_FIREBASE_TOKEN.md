# How to Get Firebase ID Token for Testing

The authenticated endpoints require a Firebase ID token. Here are several ways to get one:

## Option 1: From Browser (Easiest)

1. Login to your Aneya app at https://aneya.vercel.app
2. Open browser DevTools (F12)
3. Go to **Application** tab → **IndexedDB** → **firebaseLocalStorage**
4. Find the entry for your Firebase project
5. Copy the value of `stsTokenManager.accessToken`
6. Export it in your terminal:
   ```bash
   export FIREBASE_ID_TOKEN='eyJhbGciOiJSUzI1NiIsImtpZCI6...'
   ```

## Option 2: Using Firebase Auth REST API

```bash
# Replace with your Firebase Web API Key
API_KEY="your-firebase-web-api-key"

# Replace with test user credentials
EMAIL="test@example.com"
PASSWORD="testpassword123"

# Get ID token
curl -X POST "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$API_KEY" \
  -H 'Content-Type: application/json' \
  -d "{
    \"email\": \"$EMAIL\",
    \"password\": \"$PASSWORD\",
    \"returnSecureToken\": true
  }" | jq -r '.idToken'

# Export the token
export FIREBASE_ID_TOKEN='<token-from-above>'
```

## Option 3: Using Firebase Admin SDK (Python)

```python
import firebase_admin
from firebase_admin import auth, credentials

# Initialize Firebase Admin
cred = credentials.Certificate("path/to/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# Create custom token for test user
uid = "test-user-uid"
custom_token = auth.create_custom_token(uid)

# Exchange custom token for ID token (via Firebase Auth REST API)
# ... (requires additional HTTP request)
```

## Testing Commands

Once you have the token exported:

```bash
# Run authenticated tests
python test_authenticated_form_filling.py

# Or set it inline
FIREBASE_ID_TOKEN='your-token' python test_authenticated_form_filling.py
```

## Token Expiration

Firebase ID tokens expire after **1 hour**. If you get a 401 error, refresh your token using one of the methods above.
