---
sidebar_position: 2
---

# Flutter Push Add-on

The `synkora_push` package extends the Flutter chat experience with FCM-based notifications for agent replies.

## Package

Use the `synkora_push` package together with `synkora_chat`.

## Typical Flow

1. initialize Firebase in the Flutter app
2. initialize `SynkoraPush`
3. connect it to the active conversation source
4. handle foreground and background notifications

## Best Fit

Use the push add-on when agent conversations continue after the app is backgrounded and you want users to be notified of replies.
