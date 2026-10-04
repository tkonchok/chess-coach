# Configure live Google and Groq locally

These steps configure development accounts, not a public deployment. Keep credentials on your computer and out of chat. Use one exact address throughout: **http://127.0.0.1:5050**. Do not switch to `localhost` during an OAuth attempt.

## 1. Google sign-in

1. Open [Google Cloud Console](https://console.cloud.google.com/) and select or create a project named Chess Coach.
2. Open **Google Auth Platform → Branding**. Set the app name, user support email and developer contact. Use **Audience → External** for personal accounts. Keep the app in testing and add your email under **Test users**; add a second account for ownership checks if available.
3. Under **Data Access**, use only the basic OpenID/email sign-in scopes. This application requests `openid email`; it does not need access to Gmail, Drive or Calendar.
4. Open **Clients → Create client** and choose **Web application**. Name it Chess Coach Local.
5. Add this exact **Authorized redirect URI**: `http://127.0.0.1:5050/auth/google/callback`. If the console asks for an authorized JavaScript origin, use `http://127.0.0.1:5050`; this implementation uses the server OAuth flow.
6. Create the client. Save its client ID and client secret privately. Use the OAuth client, not a service-account key. No Google API billing purchase is part of this setup.

The project/client, consent screen and exact callback requirements are described in [Google's OpenID Connect setup](https://developers.google.com/identity/openid-connect/openid-connect). The basic consent/test-user process is documented in [Google's consent configuration guide](https://developers.google.com/workspace/guides/configure-oauth-consent). If your account shows different navigation, use the console search for Google Auth Platform or OAuth clients.

## 2. Groq free-tier key

Open [Groq Console API keys](https://console.groq.com/keys), sign in, and create a key named Chess Coach Local. Keep the account on its free plan for this project. Copy the key into local configuration, not chat. Leave the model as `openai/gpt-oss-120b` initially; availability and free-tier limits are account-dependent. See [Groq quickstart](https://console.groq.com/docs/quickstart) and [structured output support](https://console.groq.com/docs/structured-outputs).

## 3. Store configuration privately

From the project directory, copy the example once (do not overwrite a configured file):

```sh
cp -n .env.example .env
chmod 600 .env
```

Open `.env` in your editor and fill these values. Single-quote credentials so the shell treats them literally:

```sh
APP_ORIGIN='http://127.0.0.1:5050'
SECRET_KEY='your-persistent-random-secret'
GOOGLE_CLIENT_ID='your-client-id.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET='your-client-secret'
GROQ_API_KEY='your-groq-key'
GROQ_MODEL='openai/gpt-oss-120b'
LOCAL_DEMO=0
LOCAL_TESTING=1
AUTOMATIC_EXERCISES_ENABLED=1
DATABASE='instance/chess-coach.sqlite3'
STOCKFISH_PATH='stockfish'
```

Generate the session secret locally using `python3 -c "import secrets; print(secrets.token_hex(32))"` and paste it into the file. Do not put credentials directly into terminal commands that will enter shell history. `.env` and `.env.*` are ignored; `.env.example` contains placeholders only. The preparation flag above is for local quality evaluation; keep it disabled publicly until review passes.

## 4. Start with the credentials loaded

Flask does not auto-load this file in this project. In the same terminal:

```sh
set -a
source .env
set +a
.venv/bin/python -m flask --app 'chess_coach.beta:create_app()' run --host 127.0.0.1 --port 5050
```

Do not enable Flask's reloader: the single-supervisor lock intentionally rejects multiple application processes. Stop any previous server first. Keep the terminal running and open http://127.0.0.1:5050.

## 5. Verify real behavior

Select **Continue with Google**, approve basic sign-in, and confirm you return to the games page. Log out, check that private pages require sign-in, then sign in again. Import your Chess.com username and explicitly select a recent rapid game; preserve coverage warnings. If no suitable position is found, use a different day's game or evaluate the real-game fixtures with a separate local test account; never relax selection to fabricate a result. Local testing permits 20 analyses and 20 imports/account/day when `LOCAL_TESTING=1`; the global daily cap and one-active-job limit still apply. Public hosting rejects this flag.

After proposing and revealing, select **Request AI explanation**. Review the actual explanation against the supplied legal line, scores and alternatives; success means accurate and useful language, not merely a JSON response. Notes must remain absent from provider payloads. Save and revisit. Complete the six-position review in `TEACHING_REVIEW.md` before enabling automatic practice for public users.

`redirect_uri_mismatch` means the console callback and app origin differ. A missing sign-in button means the environment was not loaded before starting. A Google test-user denial means the account/audience configuration needs checking. Engine-only fallback on AI request means a key, model, quota, timeout or output-validation issue; it does not block saving. Do not paste keys when reporting an error.

Later, after deployment approval, add the Railway HTTPS callback to the same OAuth client and set the server's `APP_ORIGIN` to that HTTPS origin. Local credentials setup alone does not authorize publishing or purchases.
