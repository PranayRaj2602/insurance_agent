from typing import Generator, Optional
import anthropic

from src.config import ANTHROPIC_API_KEY, MODEL_ORCHESTRATOR
from src.tools.retrieval import TOOLS, execute_tool
from src.tools.document_store import DocumentStore

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_CHAT_SYSTEM = """You are an expert P&C insurance analyst assistant with deep knowledge of claims processing, policy interpretation, coverage analysis, and risk assessment.

You have access to a corpus of insurance claim documents. Use your tools to search and retrieve relevant information before answering. Always ground your answers in the actual documents.

Guidelines:
- Always search before answering factual questions about specific claims
- Cite which documents you're drawing from (claim ID and doc type)
- Be precise about coverage limits, deductibles, and claim amounts
- Flag any inconsistencies you notice between documents
- Use analyze_coverage for deep coverage gap questions
- Use compare_claims when asked to contrast two claims"""


class ChatAgent:
    def __init__(self, store: DocumentStore, summaries_cache: dict):
        self.store = store
        self.summaries_cache = summaries_cache

    def stream_response(
        self,
        user_message: str,
        history: list[dict],
        claim_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Stream a response through the agentic tool loop."""
        messages = list(history)

        # Inject claim context as a system reminder if a claim is selected
        content = user_message
        if claim_id:
            content = f"[Context: User is currently viewing claim {claim_id}]\n\n{user_message}"

        messages.append({"role": "user", "content": content})

        while True:
            with client.messages.stream(
                model=MODEL_ORCHESTRATOR,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=[{"type": "text", "text": _CHAT_SYSTEM,
                         "cache_control": {"type": "ephemeral"}}],
                tools=TOOLS,
                messages=messages,
            ) as stream:
                accumulated_text = ""
                for text in stream.text_stream:
                    accumulated_text += text
                    yield text
                response = stream.get_final_message()

            if response.stop_reason == "end_turn":
                # Add to history
                messages.append({"role": "assistant", "content": response.content})
                break

            if response.stop_reason != "tool_use":
                break

            # Execute tool calls
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            tool_results = []

            # Signal tool calls to the UI via a special marker
            for block in tool_use_blocks:
                yield f"\n\n*🔧 Using tool: `{block.name}`...*\n\n"
                result = execute_tool(
                    block.name,
                    block.input,
                    self.store,
                    self.summaries_cache,
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
