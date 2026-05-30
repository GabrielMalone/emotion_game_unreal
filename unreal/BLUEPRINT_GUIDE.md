# Unreal Blueprint Wiring for Word-Timed Text Display

This assumes your project already has SocketIO working (receiving `npc_text_token`, `npc_audio_chunk`, etc.).

## Option A — Use the C++ component (recommended)

1. Copy `WordTimingDisplayComponent.h` and `WordTimingDisplayComponent.cpp` into your project's `Source/` folder.
2. Rebuild.
3. Add `UWordTimingDisplayComponent` to your NPC actor.
4. In the NPC Blueprint:
   - (Optional) On `BeginPlay`, call `SetTextRenderComponent` with the TextRenderComponent that displays NPC dialogue.
5. Wire socket events:
   - `show_word` → parse JSON → call `OnShowWord` with the `word` string
   - `npc_audio_done` → call `OnSentenceDone`
   - `npc_audio_stop` → call `OnAudioStop`
6. **Stop** displaying text on `npc_text_token`. That event should now only be used for internal logic (storing full sentence text, etc.).

## Option B — Pure Blueprint (no C++)

If you can't add C++, do the same logic in Blueprint:

### Variable (in your NPC Blueprint)
- Add a variable: `DisplayText` (String) — the accumulated display string

### Event: `show_word`

When this socket event fires:

```
Event "show_word" (JSON string)
  → Parse JSON → get "word" field
  → Append to DisplayText: DisplayText = DisplayText + " " + word
  → Set NPC Text Widget text to DisplayText
```

### Event: `npc_audio_done`

```
  → (optional) Show full sentence for a beat, then clear DisplayText
```

### Event: `npc_audio_stop`

```
  → Clear DisplayText
  → Set NPC text widget to empty string
```

### Event: `npc_stream_audio_done`

```
  → Clear DisplayText (final cleanup)
```

### IMPORTANT: Stop showing text on `npc_text_token`

The `npc_text_token` event now arrives BEFORE the audio. Do **not** display it. Instead, just store it in a variable (e.g., `PendingFullSentence`) for other game logic.

## Sequence of events (server → Unreal)

```
npc_text_token     → "Hello! How are you?"    ← DON'T display (arrives before audio)
npc_audio_chunk    → (base64 audio)            ← plays on AudioComponent
show_word          → {"word":"Hello"}          ← append to display
show_word          → {"word":"How"}            ← append to display
show_word          → {"word":"are"}            ← append to display
show_word          → {"word":"you?"}           ← append to display
npc_audio_done     → {}                        ← sentence complete
npc_audio_chunk    → ...next sentence...
show_word          → ...
npc_audio_done     → ...
npc_stream_audio_done → {}                     ← all done
```

## How it works

The server handles all timing. It uses ElevenLabs character-level alignment data
to calculate when each word should appear relative to audio playback, then emits
`show_word` events at the right moment via a background task. Unreal simply
appends each word as it arrives — no Tick polling or `GetPlaybackTime()` needed.
