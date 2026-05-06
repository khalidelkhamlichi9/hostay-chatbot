# Documentation Intégration Chatbot Hostay (v1.0)

Cette documentation détaille l'intégration technique du chatbot Hostay dans vos interfaces de chat.

## 1. Informations Générales
- **URL de Base** : `https://m4.hostayapp.com`
- **Format d'échange** : JSON (UTF-8)
- **Sécurité** : HTTPS obligatoire

## 2. Authentification
L'API est protégée par **JWT (JSON Web Token)**. Vous devez inclure le token utilisateur dans chaque requête.

- **Header** : `Authorization: Bearer <VOTRE_JWT_TOKEN>`
- **Payload requis dans le JWT** : 
  - `role` : 'guest', 'owner' ou 'concierge' (détermine le comportement de l'IA).
  - `user_hashId` (optionnel) : Identifiant de l'utilisateur.

## 3. Endpoint Chat

### POST `/chat`
Envoie un message au chatbot et récupère une réponse générée par l'IA (RAG + LLM).

#### Requête (Body)
```json
{
  "message": "Bonjour, comment puis-je faire mon check-in ?",
  "session_id": "uuid-v4-optionnel"
}
```
- `message` (string, requis) : Le texte de l'utilisateur.
- `session_id` (string, optionnel) : Permet de maintenir le contexte de la conversation. Si non fourni, le serveur en générera un nouveau.

#### Réponse (Success 200 OK)
```json
{
  "user": {
    "role": "guest",
    "user_hashId": "123",
    "token": "..."
  },
  "reply": "Bonjour ! Pour faire votre check-in, vous recevrez un code SMS 2h avant votre arrivée...",
  "saved": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```
- `reply` : La réponse de l'IA.
- `session_id` : L'ID à renvoyer dans la prochaine requête pour garder le fil.

## 4. Sécurité & CORS
Le serveur est configuré pour n'accepter que les requêtes provenant des domaines officiels Hostay.

- **Domaines autorisés** : `hostayapp.com` et tous ses sous-domaines (`*.hostayapp.com`).
- **Comportement** : Toute requête provenant d'un domaine tiers sera bloquée par le navigateur (CORS Policy).

## 5. Exemple d'implémentation (JavaScript)

```javascript
async function askChatbot(userMessage, currentSessionId = null) {
  const token = "VOTRE_JWT_TOKEN_ICI";
  const url = "https://m4.hostayapp.com/chat";

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        message: userMessage,
        session_id: currentSessionId
      })
    });

    const data = await response.json();
    console.log("IA :", data.reply);
    return data.session_id; // À sauvegarder pour la suite
  } catch (error) {
    console.error("Erreur Chatbot:", error);
  }
}
```

## 6. Rate Limiting
Pour garantir la stabilité, une limite est appliquée par adresse IP :
- **Limite** : 20 messages par minute.
- **Dépassement** : Erreur 429 (Too Many Requests).
