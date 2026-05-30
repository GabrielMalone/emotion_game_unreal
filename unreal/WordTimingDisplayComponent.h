#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "WordTimingDisplayComponent.generated.h"

/** Single word with start/end time (seconds from sentence start). */
USTRUCT(BlueprintType)
struct FWordTiming
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly)
    FString Word;

    /** Seconds from start of this sentence's audio. */
    UPROPERTY(BlueprintReadOnly)
    float StartTime = 0.f;

    /** Seconds from start of this sentence's audio. */
    UPROPERTY(BlueprintReadOnly)
    float EndTime = 0.f;
};

/**
 * Drives a text widget word-by-word in sync with audio playback.
 * 
 * Two modes of operation:
 * 
 * A) Server-timed (recommended) — use OnShowWord:
 *    Server emits show_word → {"word":"..."} one word at a time,
 *    timed to align with audio. Unreal just appends each word.
 *    No Tick or AudioComponent needed.
 * 
 * B) Client-timed (legacy) — use OnWordTimingsReceived:
 *    Server sends full word array with start/end times.
 *    On each Tick, checks UAudioComponent playback time against
 *    stored word timings and builds a progressive display string.
 * 
 * Server events used:
 *   show_word          → {"word":"..."} — single word, append immediately
 *   npc_word_timings   → {"words": [{"word":"...","start":0.0,"end":0.5}, ...]}
 *   npc_audio_done     → clear when sentence done
 *   npc_audio_stop     → immediate clear + reset
 */
UCLASS(ClassGroup=(NPC), meta=(BlueprintSpawnableComponent))
class UWordTimingDisplayComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UWordTimingDisplayComponent();

    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
                               FActorComponentTickFunction* ThisTickFunction) override;

    // ── Blueprint-callable API ──────────────────────────────────────────

    /** Call when "show_word" socket event arrives — appends word immediately. */
    UFUNCTION(BlueprintCallable, Category = "NPC|WordTiming")
    void OnShowWord(const FString& Word);

    /** Call when "npc_word_timings" socket event arrives (legacy client-timed mode). */
    UFUNCTION(BlueprintCallable, Category = "NPC|WordTiming")
    void OnWordTimingsReceived(const TArray<FWordTiming>& Words);

    /** Call when "npc_audio_done" arrives — sentence complete. */
    UFUNCTION(BlueprintCallable, Category = "NPC|WordTiming")
    void OnSentenceDone();

    /** Call when "npc_audio_stop" arrives — flush immediately. */
    UFUNCTION(BlueprintCallable, Category = "NPC|WordTiming")
    void OnAudioStop();

    /** Set the audio component whose playback time we track. */
    UFUNCTION(BlueprintCallable, Category = "NPC|WordTiming")
    void SetAudioComponent(UAudioComponent* InAudio);

    /** Set the text render component / widget to update. */
    UFUNCTION(BlueprintCallable, Category = "NPC|WordTiming")
    void SetTextRenderComponent(UTextRenderComponent* InText);

    /** Get current display text (use in widget binding). */
    UFUNCTION(BlueprintCallable, Category = "NPC|WordTiming")
    FText GetDisplayText() const { return CurrentDisplayText; }

    // ── Events ──────────────────────────────────────────────────────────

    /** Fired every Tick with the latest display text (for widget binding). */
    DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnDisplayTextUpdated, const FText&, NewText);

    UPROPERTY(BlueprintAssignable, Category = "NPC|WordTiming")
    FOnDisplayTextUpdated OnDisplayTextUpdated;

protected:
    virtual void BeginPlay() override;

private:
    /** All word timings for current sentence. */
    UPROPERTY()
    TArray<FWordTiming> WordTimings;

    /** Audio component whose playback time we track. */
    UPROPERTY()
    TObjectPtr<UAudioComponent> AudioComponent;

    /** Optional text render component to auto-update. */
    UPROPERTY()
    TObjectPtr<UTextRenderComponent> TextRender;

    /** Current progressive display text. */
    FText CurrentDisplayText;

    /** True when we have active word timings. */
    bool bActive = false;

    void UpdateDisplay(float CurrentTime);
};
