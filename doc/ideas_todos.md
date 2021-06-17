# Ideas And Todos For Later
There is always something that should be done. In this document we collect issues and ideas for the backend/frontend.

## Backend
- [ ] use jolocom id for signup (name and email) instead of having the User input them. 
  This way we can also authenticate the email address. i.e.
  * ask for jolocom id
  * send authentication email with test link
  * user is created if testlink is clicked
- [ ] put Email sending into a separate grenlet so that it is sent asynchronously
- [ ] authenticate user signup emails
- [ ] support TLS for email sending not just SSL
- [ ] use SPHINX for automatic API documentation
- [ ] instead of an organizer credential we could use the authentication workflow and the user DID
- [ ] allow users to request new password or new login credential with their email.

# Frontend
- [ ] instead of sending Tickets immediately, offer a "send ticket" button
- [ ] as json web tokens are only valid once and expire quick, offer an easy way to re-issue them every time 
they are used as QR-codes or deep-links
- [ ] allow users to request new password or new login credential with their email.
  
# General
- [ ] look into what fields should be used for credentials
- [ ] support for linkedin
- [ ] support for qualichain
- [ ] support for ORCID

