"""
Function dispatch — routes voice agent function calls to the claims backend.

Functions defined in agent_config.py:
  submit_claim  → claims_service.submit_claim_draft()
  end_call      → signals the session to hang up after goodbye audio
"""
import logging

logger = logging.getLogger(__name__)


async def dispatch_function(name: str, args: dict, call_sid: str = "") -> dict:
    """Dispatch a function call from the agent to the appropriate handler.

    Args:
        name:     Function name (must match names in agent_config.FUNCTIONS)
        args:     Parsed arguments from the LLM
        call_sid: Current call SID — needed to associate the draft with the call

    Returns:
        Result dict sent back to the agent as context for its next response.
    """
    if name == "submit_claim":
        from backend.claims_service import submit_claim_draft
        claim_ref = await submit_claim_draft(call_sid, args)
        logger.info(f"[CLAIMS] Claim submitted for {call_sid}: {claim_ref}")
        return {
            "status": "submitted",
            "claim_ref": claim_ref,
            "message": (
                f"Claim {claim_ref} has been opened successfully. "
                "The caller will receive email confirmation and an assessor "
                "will be in touch within one business day."
            ),
        }

    elif name == "end_call":
        reason = args.get("reason", "caller_goodbye")
        logger.info(f"[CLAIMS] end_call requested — reason: {reason}")
        return {"status": "call_ending", "reason": reason}

    else:
        logger.warning(f"Unknown function: {name}")
        return {"error": f"Unknown function: {name}"}
