# 🔐 Security Policy

## 📌 Supported Versions

The following versions of Sanctified Backend are currently supported with security updates:

| Version        | Supported |
| -------------- | --------- |
| main (latest)  | ✅ Yes     |
| Older releases | ❌ No      |

We recommend always using the latest version from the `main` branch.

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do NOT open a public issue.**

Instead, please:

1. Email: [lenoxtechbro@proton.me](mailto:lenoxtechbro@proton.me)
2. Include detailed steps to reproduce the issue
3. Provide proof-of-concept if possible
4. Allow up to 72 hours for initial response

You will receive acknowledgment within 72 hours.

---

## 🔒 Responsible Disclosure Policy

We ask that you:

* Do not publicly disclose the vulnerability before it is fixed
* Do not exploit the vulnerability beyond proof-of-concept
* Do not access or modify data that does not belong to you

We are committed to:

* Acknowledging your report
* Investigating promptly
* Releasing a patch if valid
* Crediting you (if you wish)

---

## 🛡 Security Practices

This project follows best practices including:

* Environment variable protection (.env not committed)
* Input validation using Pydantic
* Secure dependency version pinning
* Server-to-server verification for payment webhooks
* HTTPS enforced in production

---

Thank you for helping keep Sanctified Backend secure.
