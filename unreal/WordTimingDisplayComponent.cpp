#include "WordTimingDisplayComponent.h"
#include "Components/AudioComponent.h"
#include "Components/TextRenderComponent.h"

UWordTimingDisplayComponent::UWordTimingDisplayComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
}

void UWordTimingDisplayComponent::BeginPlay()
{
    Super::BeginPlay();
}

void UWordTimingDisplayComponent::TickComponent(float DeltaTime, ELevelTick TickType,
                                                 FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

    if (!bActive || !AudioComponent)
    {
        return;
    }

    // Get current playback position in seconds
    float CurrentTime = AudioComponent->GetPlaybackTime();
    if (CurrentTime < 0.f)
    {
        CurrentTime = 0.f;
    }

    UpdateDisplay(CurrentTime);
}

// ─────────────────────────────────────────────────────────────────────
// Blueprint API
// ─────────────────────────────────────────────────────────────────────

void UWordTimingDisplayComponent::OnShowWord(const FString& Word)
{
    // Append word to current display text — server handles timing.
    FString Current = CurrentDisplayText.ToString();
    if (!Current.IsEmpty())
    {
        Current += TEXT(" ");
    }
    Current += Word;
    CurrentDisplayText = FText::FromString(Current);
    OnDisplayTextUpdated.Broadcast(CurrentDisplayText);
    if (TextRender)
    {
        TextRender->SetText(CurrentDisplayText);
    }
}

void UWordTimingDisplayComponent::OnWordTimingsReceived(const TArray<FWordTiming>& Words)
{
    WordTimings = Words;
    bActive = Words.Num() > 0;

    // Immediately show first frame (time 0 = show nothing or first word)
    UpdateDisplay(0.f);
}

void UWordTimingDisplayComponent::OnSentenceDone()
{
    // Show the full sentence one final time, then clear after a beat.
    // The audio is done, so show everything.
    FString FullText;
    for (const FWordTiming& W : WordTimings)
    {
        FullText += W.Word + TEXT(" ");
    }
    FullText.TrimEndInline();
    CurrentDisplayText = FText::FromString(FullText);
    OnDisplayTextUpdated.Broadcast(CurrentDisplayText);
    if (TextRender)
    {
        TextRender->SetText(CurrentDisplayText);
    }

    bActive = false;
    // Don't clear — let the full sentence sit.
    // npc_stream_audio_done or next npc_audio_stop will clear.
}

void UWordTimingDisplayComponent::OnAudioStop()
{
    bActive = false;
    WordTimings.Empty();
    CurrentDisplayText = FText::GetEmpty();
    OnDisplayTextUpdated.Broadcast(CurrentDisplayText);
    if (TextRender)
    {
        TextRender->SetText(CurrentDisplayText);
    }
}

void UWordTimingDisplayComponent::SetAudioComponent(UAudioComponent* InAudio)
{
    AudioComponent = InAudio;
}

void UWordTimingDisplayComponent::SetTextRenderComponent(UTextRenderComponent* InText)
{
    TextRender = InText;
}

// ─────────────────────────────────────────────────────────────────────
// Internal
// ─────────────────────────────────────────────────────────────────────

void UWordTimingDisplayComponent::UpdateDisplay(float CurrentTime)
{
    FString DisplayString;

    for (const FWordTiming& W : WordTimings)
    {
        if (W.StartTime <= CurrentTime)
        {
            DisplayString += W.Word + TEXT(" ");
        }
    }

    DisplayString.TrimEndInline();
    FText NewText = FText::FromString(DisplayString);

    if (!CurrentDisplayText.EqualTo(NewText))
    {
        CurrentDisplayText = NewText;
        OnDisplayTextUpdated.Broadcast(CurrentDisplayText);

        if (TextRender)
        {
            TextRender->SetText(CurrentDisplayText);
        }
    }
}
