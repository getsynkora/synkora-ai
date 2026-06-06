# Mobile iOS Release CI/CD

This repository now supports a tag-driven mobile release workflow in [.github/workflows/mobile-release.yml](/Users/raju/Sites/ai-automation/synkora/.github/workflows/mobile-release.yml).

## Trigger

Push a tag in this format:

```bash
git tag mobile/v1.2.3
git push origin mobile/v1.2.3
```

What happens on that tag:

- creates a GitHub release
- builds signed Android APK and AAB artifacts
- builds a signed iOS archive and IPA
- uploads the iOS IPA to TestFlight
- optionally submits the uploaded iOS build to App Store review

`workflow_dispatch` is also supported for manual releases.

## GitHub Variables

Set these in `Settings -> Secrets and variables -> Actions -> Variables`.

`MOBILE_API_URL`
- Example: `https://api.synkora.ai`
- Passed into the Flutter app as `SYNKORA_API_URL`

`IOS_APP_BUNDLE_ID`
- Example: `ai.synkora.mobile`
- Must match the bundle identifier in App Store Connect, the provisioning profile, and the distribution certificate setup

`IOS_APPLE_TEAM_ID`
- Example: `ABCDE12345`
- Your Apple Developer Team ID

`IOS_APP_STORE_APP_ID`
- Example: `1234567890`
- The numeric App Store Connect Apple ID for the iOS app

`IOS_AUTO_SUBMIT_TO_APP_STORE`
- `true` or `false`
- If `true`, the workflow submits the uploaded TestFlight build to App Store review after processing

`IOS_AUTO_RELEASE_ON_APPROVAL`
- `true` or `false`
- If `true`, the App Store build is released automatically after Apple approves it
- If `false`, it is submitted for review but release remains manual

## GitHub Secrets

Set these in `Settings -> Secrets and variables -> Actions -> Secrets`.

`IOS_APP_STORE_CONNECT_API_KEY_ID`
- App Store Connect API key ID

`IOS_APP_STORE_CONNECT_ISSUER_ID`
- App Store Connect API issuer ID

`IOS_APP_STORE_CONNECT_API_KEY_BASE64`
- Base64-encoded `.p8` App Store Connect API key content

`IOS_DISTRIBUTION_CERT_BASE64`
- Base64-encoded iOS distribution certificate in `.p12` format

`IOS_DISTRIBUTION_CERT_PASSWORD`
- Password for the `.p12` certificate

`IOS_PROVISIONING_PROFILE_BASE64`
- Base64-encoded App Store provisioning profile (`.mobileprovision`)

`ANDROID_KEYSTORE_BASE64`
- Base64-encoded Android release keystore

`ANDROID_KEYSTORE_PASSWORD`
- Android keystore password

`ANDROID_KEY_ALIAS`
- Android signing key alias

`ANDROID_KEY_PASSWORD`
- Android signing key password

## How To Generate Base64 Secrets

Use these locally before pasting values into GitHub.

```bash
base64 -i AuthKey_ABC123XYZ.p8 | pbcopy
base64 -i SynkoraDistribution.p12 | pbcopy
base64 -i SynkoraAppStore.mobileprovision | pbcopy
base64 -i upload-keystore.jks | pbcopy
```

## Apple Requirements

Before the workflow can complete successfully, make sure:

- the iOS app record already exists in App Store Connect
- the bundle ID in App Store Connect matches `IOS_APP_BUNDLE_ID`
- the provisioning profile is an App Store profile for that exact bundle ID
- the `.p12` certificate matches the provisioning profile
- App Store metadata required for submission already exists in App Store Connect

## Notes

- iOS build numbers are generated from the GitHub run number and run attempt, so reruns still get a unique build number.
- App Store submission is intentionally controlled by `IOS_AUTO_SUBMIT_TO_APP_STORE`. Leave it `false` until the listing is ready.
- The current iOS project still uses the default local bundle ID in Xcode. CI overrides that for signed release builds using `IOS_APP_BUNDLE_ID`.
