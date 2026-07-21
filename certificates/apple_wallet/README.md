# Certificates Directory Guide

This directory contains Apple Wallet Pass Certificate credentials and Signing Requests.

## Files

1. `CertificateSigningRequest.certSigningRequest` — Certificate Signing Request generated via Keychain Access.
2. `pass.cer` — Downloaded Pass Type ID Certificate from Apple Developer Portal.
3. `pass.p12` — Exported PKCS12 bundle containing Private Key + `pass.cer`.
4. `AppleWWDRCA.cer` — Apple Worldwide Developer Relations Intermediate Certificate (G3/G4).

## Certificate Workflow

1. Generate CSR via **Keychain Access** > **Certificate Assistant** > **Request a Certificate from a Certificate Authority**.
2. Upload CSR to **Apple Developer Portal** under **Pass Type IDs** to obtain `pass.cer`.
3. Import `pass.cer` into Keychain Access.
4. Export private key + certificate as `pass.p12`.
5. Download WWDR CA certificate as `AppleWWDRCA.cer`.
