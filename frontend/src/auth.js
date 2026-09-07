// Cognito Hosted UI authentication (Authorization Code flow).
//
// Flow:
//   1. signIn() redirects the browser to the Cognito Hosted UI.
//   2. Cognito redirects back to VITE_REDIRECT_URI with ?code=...
//   3. handleRedirectCallback() exchanges the code for tokens and stores them.
//   4. getIdToken() returns the stored JWT to attach to API requests.

const COGNITO_DOMAIN = import.meta.env.VITE_COGNITO_DOMAIN;
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID;
const REDIRECT_URI = import.meta.env.VITE_REDIRECT_URI || window.location.origin + '/';

const TOKEN_KEY = 'healthlab_id_token';

export function signIn() {
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    response_type: 'code',
    scope: 'openid email profile',
    redirect_uri: REDIRECT_URI,
  });
  window.location.href = `${COGNITO_DOMAIN}/login?${params.toString()}`;
}

export function signOut() {
  localStorage.removeItem(TOKEN_KEY);
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    logout_uri: REDIRECT_URI,
  });
  window.location.href = `${COGNITO_DOMAIN}/logout?${params.toString()}`;
}

export function getIdToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function isAuthenticated() {
  const token = getIdToken();
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

// Exchange the authorization code (in the URL) for tokens.
export async function handleRedirectCallback() {
  const url = new URL(window.location.href);
  const code = url.searchParams.get('code');
  if (!code) return false;

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: CLIENT_ID,
    code,
    redirect_uri: REDIRECT_URI,
  });

  const res = await fetch(`${COGNITO_DOMAIN}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  });

  if (!res.ok) throw new Error('Token exchange failed');
  const tokens = await res.json();
  localStorage.setItem(TOKEN_KEY, tokens.id_token);

  // Clean the ?code=... out of the URL bar
  window.history.replaceState({}, document.title, REDIRECT_URI);
  return true;
}
