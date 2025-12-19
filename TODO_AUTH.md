# Firebase Authentication Implementation Plan

## Overview
Implement JWT-based user authentication using Firebase Auth to secure the Cloud Run backend.

## Steps

### 1. Firebase Console Setup
- [ ] Go to https://console.firebase.google.com/
- [ ] Add existing GCP project `aneya-480607` to Firebase
- [ ] Navigate to Authentication > Sign-in method
- [ ] Enable Email/Password provider
- [ ] (Optional) Enable Google sign-in provider
- [ ] Go to Project Settings > General > Add Web App
- [ ] Copy the Firebase config (apiKey, authDomain, projectId, etc.)

### 2. Frontend Changes (aneya-frontend)
- [ ] Install Firebase SDK: `npm install firebase`
- [ ] Create `src/lib/firebase.ts` with config
- [ ] Create `src/context/AuthContext.tsx` for auth state management
- [ ] Create `src/components/LoginForm.tsx` component
- [ ] Create `src/components/SignupForm.tsx` component
- [ ] Wrap app in AuthProvider
- [ ] Add login/logout UI to header
- [ ] Update API calls to include JWT token in Authorization header

### 3. Backend Changes (aneya-backend)
- [ ] Add `firebase-admin` to requirements.txt
- [ ] Create `auth/firebase_auth.py` middleware
- [ ] Initialize Firebase Admin SDK in api.py
- [ ] Add JWT validation dependency to protected routes
- [ ] Keep /health endpoint public (for Cloud Run health checks)

### 4. Deployment
- [ ] Add Firebase service account to Cloud Run secrets
- [ ] Update Cloud Run with new image
- [ ] Test authentication flow end-to-end
- [ ] Remove public access, require authentication

## Firebase Config Template
```javascript
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "aneya-480607.firebaseapp.com",
  projectId: "aneya-480607",
  storageBucket: "aneya-480607.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};
```

## Notes
- Firebase Auth is free for up to 50k monthly active users
- JWTs expire after 1 hour by default, Firebase SDK handles refresh
- Backend validates JWT signature using Google's public keys (no shared secret needed)
