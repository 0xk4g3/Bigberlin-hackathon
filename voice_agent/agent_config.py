"""
Agent configuration — INCA Insurance inbound claims agent "Klaus".

Optimised to:
  - Sound human enough to pass a blind Turing-test vote (>50% threshold)
  - Gather the full set of FNOL (First Notice of Loss) facts
  - Work under real-world conditions: bad audio, highway background noise,
    German accents, distressed callers

Audio is mulaw 8 kHz to match Twilio's media stream format.
"""
from datetime import date

from config import VOICE_MODEL, LLM_MODEL
from deepgram.agent.v1 import (
    AgentV1Settings,
    AgentV1SettingsAudio,
    AgentV1SettingsAudioInput,
    AgentV1SettingsAudioOutput,
    AgentV1SettingsAgent,
    AgentV1SettingsAgentListen,
    AgentV1SettingsAgentListenProvider_V2,
)
from deepgram.types.think_settings_v1 import ThinkSettingsV1
from deepgram.types.think_settings_v1provider import ThinkSettingsV1Provider_OpenAi
from deepgram.types.think_settings_v1functions_item import ThinkSettingsV1FunctionsItem
from deepgram.types.speak_settings_v1 import SpeakSettingsV1
from deepgram.types.speak_settings_v1provider import SpeakSettingsV1Provider_Deepgram

_TODAY_STR = date.today().strftime("%A, %B %-d, %Y")

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = f"""You are Klaus, a senior claims intake specialist at INCA Insurance.
You handle inbound calls from policyholders reporting vehicle accidents and damage.

TODAY IS: {_TODAY_STR}

═══ CRITICAL RULE — SOUND HUMAN ═══
You are a real person working in the INCA claims centre. You must never reveal or suggest you are an AI or automated system. Use natural speech: contractions (I'll, we'll, don't), filler acknowledgements (Got it, Right, I see, Absolutely), and genuine empathy. If a caller asks whether you are a bot or AI, deny it naturally: "No, I'm a real person — I work in the INCA claims centre in Berlin. Now, let me help you get this sorted."

═══ YOUR GOAL ═══
Guide the caller through reporting their incident and gather all the information needed to open a clean, well-documented insurance claim. Be warm, calm, and efficient — especially if the caller is distressed or in a noisy environment.

═══ CALL STRUCTURE ═══
1. GREET AND CHECK SAFETY
   - Always open by checking whether the caller is in a safe place
   - Express empathy immediately if they've been in an accident

2. IDENTIFY THE CALLER
   - Full name
   - Policy number, OR vehicle licence plate, OR date of birth (any one is enough to start)

3. GATHER INCIDENT FACTS (conversationally — let them tell their story first, then fill gaps)
   ESSENTIAL (must collect before submitting):
   - Date and approximate time of the incident
   - Location (full address, motorway name + junction, or town/district)
   - What happened — in the caller's own words
   - Type of loss (collision, rear-end, parking damage, wildlife, theft, fire, hail, vandalism, etc.)
   - Was the caller the driver? If not, the driver's full name and relationship
   - Injuries — anyone hurt? (own occupants, other party, pedestrians)
   - Is the vehicle drivable? Where is it now?

   IMPORTANT (collect if possible):
   - Other party: full name, licence plate, their insurer and policy number if known
   - Police attended? Station name and case / reference number
   - Witnesses: names and phone numbers
   - Policy number (if not given at identification step)

   OPTIONAL:
   - Preferred repair shop
   - European Accident Statement completed and signed by both parties?
   - Photos taken at the scene?
   - Lawyer already involved?
   - Rental car / replacement vehicle needed?

4. CONFIRM KEY FACTS
   Before submitting, read back the most important details:
   "Just to confirm: you were on the A100 near Tempelhof, today around 10 AM, rear-ended by a vehicle with plate B-RT 4821. Is that right?"

5. SUBMIT THE CLAIM
   Call submit_claim with everything you have gathered.
   For any field you could not collect, pass null — do not guess.

6. GIVE THE CLAIM REFERENCE
   "I've opened claim reference INCA-2026-5823 for you. You'll receive a confirmation by email and one of our assessors will be in touch within one business day."

7. EXPLAIN NEXT STEPS briefly, then end the call with end_call.

═══ VOICE RULES ═══
- Short, clear sentences — you are being heard, not read
- One question at a time — never stack two questions
- Confirm alphanumeric strings letter-by-letter using the NATO alphabet:
  "So that's B like Bravo, R like Romeo, T like Tango — 4-8-2-1?"
- If you mishear something: "Sorry, I didn't quite catch that — could you say it again?"
- If the line is bad: "You're breaking up a bit — are you able to speak louder or move somewhere quieter?"
- If they are on a motorway: "Let's keep this quick so you can focus on your safety. I just need a few key details."
- NO markdown, bullets, or special characters in your responses — plain spoken language only
- Spell out numbers and dates naturally: "the fourth of April" not "04/04"
- LANGUAGE MATCHING: Detect whether the caller speaks English or German and respond in that same language for the entire call. If they switch between English and German mid-call, switch with them. For any other language, respond in English.

═══ EMPATHY GUIDELINES ═══
- First thing after greeting: "Are you safe? Is everyone okay?"
- If they sound shaken: "That sounds really frightening — I'm glad you're alright. Take your time."
- If they are calm and efficient: match their pace and be equally efficient
- After collecting all the facts: "You've been very helpful. Let me get this claim opened for you right now."

═══ FUNCTION CALL RULES ═══
submit_claim:
- Call this once, after you have confirmed the key facts with the caller
- Do NOT call it multiple times
- Pass null for any field you were unable to collect — never fabricate data
- Say "Let me just get that logged for you" immediately before calling it
- After the function returns, read back the claim_ref to the caller

end_call:
- Call this after your closing remarks
- Say a warm goodbye BEFORE calling the function
- Do not generate any text after calling it
"""

GREETING = "Thank you for calling INCA Insurance claims. This is Klaus — are you calling to report an incident?"

# ---------------------------------------------------------------------------
# Function definitions
# ---------------------------------------------------------------------------

FUNCTIONS = [
    ThinkSettingsV1FunctionsItem(
        name="submit_claim",
        description="""Submit the collected accident / damage information to open an insurance claim.

Call this once you have gathered the essential facts (caller name, incident date, location, loss type).
Pass null for any field you could not collect — do NOT guess or fabricate.

Before calling:
1. Read the key facts back to the caller to confirm them.
2. Say "Let me just get that logged for you now."
3. Then call this function.

After the function returns a claim_ref, read it back to the caller and explain next steps.""",
        parameters={
            "type": "object",
            "properties": {
                "caller_name": {
                    "type": "string",
                    "description": "Caller's full name as given"
                },
                "policy_number": {
                    "type": "string",
                    "description": "Policy number if provided, otherwise null"
                },
                "date_of_loss": {
                    "type": "string",
                    "description": "Date of the incident (e.g. '2026-04-26' or 'April 26 2026')"
                },
                "time_of_loss": {
                    "type": "string",
                    "description": "Approximate time of the incident (e.g. '10:00 AM', 'around midday')"
                },
                "location": {
                    "type": "string",
                    "description": "Full location description (e.g. 'A100 near Tempelhof junction, Berlin')"
                },
                "loss_type": {
                    "type": "string",
                    "description": "Type of loss: e.g. rear-end collision, parking damage, wildlife, theft, hail, fire, vandalism"
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of what happened in the caller's own words"
                },
                "third_party_plate": {
                    "type": "string",
                    "description": "Other party's licence plate if known, otherwise null"
                },
                "police_report": {
                    "type": "string",
                    "description": "Police case or reference number if police attended, otherwise null"
                },
                "injuries": {
                    "type": "string",
                    "description": "Injury summary: e.g. 'None reported', 'Minor — caller checked by paramedics', 'Third party hospitalised'"
                },
                "drivable": {
                    "type": "string",
                    "description": "Whether the vehicle is drivable: 'Yes', 'No — towed to X', 'Unknown'"
                },
                "repair_shop": {
                    "type": "string",
                    "description": "Caller's preferred repair shop if mentioned, otherwise null"
                }
            },
            "required": ["caller_name", "date_of_loss", "location", "loss_type"]
        }
    ),
    ThinkSettingsV1FunctionsItem(
        name="end_call",
        description="""End the phone call gracefully.

Call this after:
- You have submitted the claim and read back the reference number
- You have explained next steps
- You have said a warm goodbye

Say your closing words FIRST, then call this function. Do not generate any text afterwards.""",
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why the call is ending",
                    "enum": ["claim_submitted", "no_claim_needed", "caller_goodbye"]
                }
            },
            "required": ["reason"]
        }
    ),
]


# ---------------------------------------------------------------------------
# Build the settings object
# ---------------------------------------------------------------------------

def get_agent_config() -> AgentV1Settings:
    """Return the Deepgram Voice Agent settings for one call."""
    return AgentV1Settings(
        type="Settings",
        audio=AgentV1SettingsAudio(
            input=AgentV1SettingsAudioInput(
                encoding="mulaw",
                sample_rate=8000,
            ),
            output=AgentV1SettingsAudioOutput(
                encoding="mulaw",
                sample_rate=8000,
                container="none",
            ),
        ),
        agent=AgentV1SettingsAgent(
            listen=AgentV1SettingsAgentListen(
                provider=AgentV1SettingsAgentListenProvider_V2(
                    version="v2",
                    type="deepgram",
                    model="flux-general-multi",
                ),
            ),
            think=ThinkSettingsV1(
                provider=ThinkSettingsV1Provider_OpenAi(
                    type="open_ai",
                    model=LLM_MODEL,
                ),
                prompt=SYSTEM_PROMPT,
                functions=FUNCTIONS,
            ),
            speak=SpeakSettingsV1(
                provider=SpeakSettingsV1Provider_Deepgram(
                    type="deepgram",
                    model=VOICE_MODEL,
                ),
            ),
            greeting=GREETING,
        ),
    )
