"""
Context Management System for Agent Conversations.

Implements multiple strategies for managing conversation context:
- Sliding Window: Keep only recent messages
- Summarization: Compress old context
- Hierarchical Memory: Different retention for different info
- RAG-style Retrieval: Store and retrieve relevant context
- Incremental Building: Efficient context updates
"""

import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class ContextStrategy(StrEnum):
    """Context management strategies."""

    SLIDING_WINDOW = "sliding_window"
    SUMMARIZATION = "summarization"
    HIERARCHICAL = "hierarchical"
    RAG_RETRIEVAL = "rag_retrieval"
    COMBINED = "combined"


class MemoryPriority(StrEnum):
    """Memory retention priority levels."""

    PERMANENT = "permanent"  # Always kept
    MEDIUM_TERM = "medium_term"  # Session-based
    SHORT_TERM = "short_term"  # Last N turns


@dataclass
class ContextConfig:
    """Configuration for context management."""

    strategy: ContextStrategy = ContextStrategy.COMBINED
    max_tokens: int = 180000  # Stay under Claude's limit
    sliding_window_size: int = 15  # Last N messages (reduced for efficiency)
    summarization_threshold: int = 100000  # Trigger summarization
    keep_recent_messages: int = 15  # Messages to keep when summarizing (increased for Slack thread context)
    hierarchical_short_term_size: int = 15  # Recent detailed messages
    rag_enabled: bool = True
    rag_top_k: int = 5  # Number of relevant contexts to retrieve

    # Auto-summarization settings (increased thresholds for better Slack thread context retention)
    auto_summarize: bool = True
    summarize_threshold_messages: int = 25  # Summarize after 25 messages (increased from 10)
    summarize_threshold_tokens: int = 30000  # Or 30k tokens (increased from 15k)
    summary_max_tokens: int = 1500  # Slightly larger summaries for better context

    # Incremental summarization
    incremental_threshold_messages: int = 5  # Re-summarize after 5 new messages


@dataclass
class ContextItem:
    """A single context item with metadata."""

    content: str
    priority: MemoryPriority
    timestamp: float
    token_count: int
    metadata: dict[str, Any]
    item_type: str  # 'message', 'preference', 'goal', 'decision', etc.


@dataclass
class IncrementalContextState:
    """State for incremental context building."""

    conversation_id: str | None = None
    last_message_count: int = 0
    last_token_count: int = 0
    last_summary: str | None = None
    last_summary_at: float | None = None
    cached_context: dict[str, Any] | None = None


class ContextManager:
    """Manages conversation context using multiple strategies."""

    def __init__(self, config: ContextConfig | None = None):
        """
        Initialize context manager.

        Args:
            config: Context management configuration
        """
        self.config = config or ContextConfig()
        self.permanent_context: list[ContextItem] = []
        self.medium_term_context: list[ContextItem] = []
        self.short_term_context: list[ContextItem] = []

        # Incremental context state
        self._incremental_state = IncrementalContextState()

        logger.info(f"ContextManager initialized with strategy: {self.config.strategy}")

    def estimate_tokens(self, text: str, model: str = "gpt-4") -> int:
        """
        Estimate token count for text using accurate TokenCounter.

        Args:
            text: Text to estimate
            model: Model name for encoding selection

        Returns:
            Token count
        """
        try:
            from src.services.agents.token_counter import TokenCounter

            return TokenCounter.count_tokens(text, model)
        except ImportError:
            return len(text) // 4

    def count_messages_tokens(self, messages: list[dict[str, str]], model: str = "gpt-4") -> int:
        """
        Count tokens for a list of messages.

        Args:
            messages: List of message dicts
            model: Model name for encoding selection

        Returns:
            Total token count
        """
        try:
            from src.services.agents.token_counter import TokenCounter

            return TokenCounter.count_messages_tokens(messages, model)
        except ImportError:
            total = 0
            for msg in messages:
                total += len(msg.get("content", "")) // 4
            return total

    def add_context(
        self, content: str, priority: MemoryPriority, item_type: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Add context item to appropriate memory tier.

        Args:
            content: Context content
            priority: Memory priority level
            item_type: Type of context item
            metadata: Additional metadata
        """
        item = ContextItem(
            content=content,
            priority=priority,
            timestamp=time.time(),
            token_count=self.estimate_tokens(content),
            metadata=metadata or {},
            item_type=item_type,
        )

        if priority == MemoryPriority.PERMANENT:
            self.permanent_context.append(item)
        elif priority == MemoryPriority.MEDIUM_TERM:
            self.medium_term_context.append(item)
        else:
            self.short_term_context.append(item)

            # Trim short-term if needed
            if len(self.short_term_context) > self.config.hierarchical_short_term_size:
                self.short_term_context.pop(0)

    def apply_sliding_window(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """
        Apply sliding window strategy.

        Args:
            messages: Full conversation history

        Returns:
            Recent messages within window
        """
        window_size = self.config.sliding_window_size
        if len(messages) <= window_size:
            return messages

        result = messages[-window_size:]
        logger.info(
            f"Sliding window applied: {len(result)}/{len(messages)} messages "
            f"(saved {len(messages) - len(result)} messages)"
        )
        return result

    def should_summarize(
        self,
        messages: list[dict[str, str]],
        existing_summary: str | None = None,
        summary_message_count: int = 0,
    ) -> bool:
        """
        Determine if messages should be summarized.

        Args:
            messages: Current messages
            existing_summary: Existing summary if any
            summary_message_count: Message count when last summary was generated

        Returns:
            True if summarization is recommended
        """
        if not self.config.auto_summarize:
            return False

        current_count = len(messages)

        # If no summary exists, check initial thresholds
        if not existing_summary:
            if current_count >= self.config.summarize_threshold_messages:
                return True

            total_tokens = self.count_messages_tokens(messages)
            if total_tokens >= self.config.summarize_threshold_tokens:
                return True

            return False

        # If summary exists, check if incremental update is needed
        messages_since_summary = current_count - summary_message_count
        if messages_since_summary >= self.config.incremental_threshold_messages:
            logger.info(
                f"Incremental summarization needed: {messages_since_summary} messages "
                f"since last summary (threshold: {self.config.incremental_threshold_messages})"
            )
            return True

        return False

    async def maybe_summarize_old_messages(
        self,
        messages: list[dict[str, str]],
        llm_client: Any,
        existing_summary: str | None = None,
        typesafe_client: Any | None = None,
    ) -> tuple[list[dict[str, str]], str | None]:
        """
        Check if summarization needed, return (recent_messages, summary).

        Strategy:
        1. If messages > threshold, summarize oldest ones
        2. Keep last N messages detailed
        3. Return summary + recent messages

        Args:
            messages: Full conversation history
            llm_client: LLM client for generating summaries
            existing_summary: Existing summary to build upon
            typesafe_client: Optional TypeSafe client. When provided, the messages
                about to be summarized are first scored for relevance and irrelevant
                ones are dropped outright (kept verbatim if relevant) before the
                remainder is summarized as usual — cheaper and avoids paraphrasing
                data the summary would otherwise blur. Omitted or any failure here
                falls straight through to the unmodified existing behavior.

        Returns:
            Tuple of (recent_messages, summary_text)
        """
        if not self.should_summarize(messages, existing_summary):
            return messages, existing_summary

        # Calculate split point
        keep_recent = self.config.keep_recent_messages
        if len(messages) <= keep_recent:
            return messages, existing_summary

        # Split messages
        messages_to_summarize = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        if typesafe_client is not None:
            try:
                from src.services.agents.context_relevance_pruner import prune_irrelevant_messages

                pruned = await prune_irrelevant_messages(messages_to_summarize, recent_messages, typesafe_client)
                if pruned is not None and len(pruned) < len(messages_to_summarize):
                    logger.info(
                        "TypeSafe pruning dropped %d/%d irrelevant messages before summarization",
                        len(messages_to_summarize) - len(pruned),
                        len(messages_to_summarize),
                    )
                    messages_to_summarize = pruned
            except Exception as exc:
                logger.warning("Relevance pruning step failed, continuing with unpruned messages: %s", exc)

        logger.info(f"Auto-summarizing {len(messages_to_summarize)} messages, keeping {len(recent_messages)} recent")

        try:
            from src.services.agents.context_summarizer import ContextSummarizer

            summarizer = ContextSummarizer(llm_client)

            # Include existing summary in context for continuity
            summary_context = ""
            if existing_summary:
                summary_context = f"Previous summary:\n{existing_summary}\n\nNew messages to incorporate:\n"

            # Generate summary
            summary = await summarizer.summarize_messages(
                messages=messages_to_summarize,
                max_summary_length=self.config.summary_max_tokens,
                context_prefix=summary_context,
            )

            logger.info(f"Generated summary ({len(summary)} chars) for {len(messages_to_summarize)} messages")

            return recent_messages, summary

        except Exception as e:
            logger.error(f"Failed to auto-summarize: {e}")
            # Fall back to just using sliding window
            return self.apply_sliding_window(messages), existing_summary

    def build_context(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        user_preferences: str | None = None,
        current_goals: str | None = None,
        relevant_history: str | None = None,
        conversation_summary: str | None = None,
        model: str = "gpt-4",
    ) -> dict[str, Any]:
        """
        Build context using combined approach with hierarchical memory.

        Memory Hierarchy:
        - PERMANENT: System prompt, user preferences, goals (always included)
        - LONG-TERM: Conversation summaries (compressed older context)
        - MEDIUM-TERM: Retrieved relevant history (RAG results)
        - SHORT-TERM: Recent messages (sliding window)

        Args:
            system_prompt: System prompt
            messages: Conversation messages
            user_preferences: User preferences (permanent)
            current_goals: Current goals (permanent)
            relevant_history: Retrieved relevant history (RAG)
            conversation_summary: Summary of older messages (long-term)
            model: Model name for token counting

        Returns:
            Dict with context parts and metadata
        """
        context_parts = []
        token_count = 0

        # === PERMANENT MEMORY (always included) ===
        if system_prompt:
            context_parts.append({"type": "system_prompt", "content": system_prompt, "memory_tier": "permanent"})
            token_count += self.estimate_tokens(system_prompt, model)

        if user_preferences:
            context_parts.append({"type": "user_preferences", "content": user_preferences, "memory_tier": "permanent"})
            token_count += self.estimate_tokens(user_preferences, model)

        if current_goals:
            context_parts.append({"type": "current_goals", "content": current_goals, "memory_tier": "permanent"})
            token_count += self.estimate_tokens(current_goals, model)

        # Include any stored permanent context items
        for item in self.permanent_context:
            context_parts.append(
                {"type": item.item_type, "content": item.content, "memory_tier": "permanent", "metadata": item.metadata}
            )
            token_count += item.token_count

        # === LONG-TERM MEMORY (conversation summaries) ===
        if conversation_summary:
            context_parts.append(
                {"type": "conversation_summary", "content": conversation_summary, "memory_tier": "long_term"}
            )
            token_count += self.estimate_tokens(conversation_summary, model)

        # === MEDIUM-TERM MEMORY (RAG results, session context) ===
        if relevant_history and self.config.rag_enabled:
            context_parts.append(
                {"type": "relevant_history", "content": relevant_history, "memory_tier": "medium_term"}
            )
            token_count += self.estimate_tokens(relevant_history, model)

        # Include any stored medium-term context items
        for item in self.medium_term_context:
            context_parts.append(
                {
                    "type": item.item_type,
                    "content": item.content,
                    "memory_tier": "medium_term",
                    "metadata": item.metadata,
                }
            )
            token_count += item.token_count

        # === SHORT-TERM MEMORY (recent messages) ===
        if self.config.strategy == ContextStrategy.SLIDING_WINDOW:
            recent_messages = self.apply_sliding_window(messages)
        elif self.config.strategy == ContextStrategy.HIERARCHICAL:
            recent_messages = self._apply_hierarchical_strategy(messages)
        else:
            # Combined approach - use sliding window
            recent_messages = self.apply_sliding_window(messages)

        # Include any stored short-term context items
        for item in self.short_term_context:
            context_parts.append(
                {
                    "type": item.item_type,
                    "content": item.content,
                    "memory_tier": "short_term",
                    "metadata": item.metadata,
                }
            )
            token_count += item.token_count

        # Estimate tokens for messages
        for msg in recent_messages:
            token_count += self.estimate_tokens(msg.get("content", ""), model)

        context_parts.append({"type": "recent_messages", "content": recent_messages, "memory_tier": "short_term"})

        # 5. Check if we need compression
        if token_count > self.config.max_tokens:
            logger.warning(
                f"Context exceeds max tokens ({token_count} > {self.config.max_tokens}), applying compression"
            )
            context_parts = self._compress_context(
                context_parts,
                target_tokens=int(self.config.max_tokens * 0.8),  # Target 80% of max
                model=model,
            )
            token_count = sum(self.estimate_tokens(str(part.get("content", "")), model) for part in context_parts)

        # Calculate memory tier statistics
        memory_stats = {
            "permanent": len(self.permanent_context),
            "long_term": 1 if conversation_summary else 0,
            "medium_term": len(self.medium_term_context) + (1 if relevant_history else 0),
            "short_term": len(self.short_term_context) + len(recent_messages),
        }

        return {
            "context_parts": context_parts,
            "estimated_tokens": token_count,
            "strategy_used": self.config.strategy.value,
            "compression_applied": token_count
            < sum(self.estimate_tokens(str(part.get("content", "")), model) for part in context_parts),
            "has_summary": conversation_summary is not None,
            "memory_stats": memory_stats,
        }

    def build_context_incremental(
        self,
        conversation_id: str,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        existing_summary: str | None = None,
        model: str = "gpt-4",
    ) -> dict[str, Any]:
        """
        Build context incrementally for efficiency.

        1. If no existing context, build from scratch
        2. If existing context, append new messages
        3. Check if compression/summarization needed
        4. Return updated context

        Args:
            conversation_id: Conversation identifier
            messages: All messages
            system_prompt: System prompt
            existing_summary: Existing conversation summary
            model: Model for token counting

        Returns:
            Context dict with incremental metadata
        """
        state = self._incremental_state

        # Check if we can use cached context
        is_same_conversation = state.conversation_id == conversation_id
        has_cached_context = state.cached_context is not None
        messages_added = len(messages) - state.last_message_count

        if is_same_conversation and has_cached_context and messages_added > 0:
            # Incremental update - only process new messages
            logger.info(f"Incremental context update: {messages_added} new messages")

            # Get new messages
            new_messages = messages[state.last_message_count :]
            new_tokens = self.count_messages_tokens(new_messages, model)

            # Update cached context
            cached = state.cached_context
            recent_messages = cached.get("context_parts", [])[-1].get("content", [])

            # Append new messages
            recent_messages.extend(new_messages)

            # Apply sliding window if needed
            if len(recent_messages) > self.config.sliding_window_size:
                recent_messages = recent_messages[-self.config.sliding_window_size :]

            # Update state
            state.last_message_count = len(messages)
            state.last_token_count += new_tokens
            cached["estimated_tokens"] = state.last_token_count
            cached["incremental_update"] = True

            return cached

        # Full rebuild needed
        logger.info(f"Full context rebuild for conversation {conversation_id}")

        context = self.build_context(
            system_prompt=system_prompt, messages=messages, conversation_summary=existing_summary, model=model
        )

        # Update incremental state
        state.conversation_id = conversation_id
        state.last_message_count = len(messages)
        state.last_token_count = context["estimated_tokens"]
        state.cached_context = context
        context["incremental_update"] = False

        return context

    def get_context_delta(self, messages: list[dict[str, str]], last_processed_position: int) -> list[dict[str, str]]:
        """
        Get only new messages since last processing.

        Args:
            messages: All messages
            last_processed_position: Position of last processed message

        Returns:
            List of new messages
        """
        return messages[last_processed_position:]

    def _apply_hierarchical_strategy(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """
        Apply hierarchical memory strategy.

        Args:
            messages: Full conversation history

        Returns:
            Messages filtered by hierarchical rules
        """
        if len(messages) <= self.config.hierarchical_short_term_size:
            return messages

        # Keep last N messages with full detail
        recent_detailed = messages[-self.config.hierarchical_short_term_size :]

        return recent_detailed

    def _compress_context(
        self, context_parts: list[dict[str, Any]], target_tokens: int, model: str = "gpt-4"
    ) -> list[dict[str, Any]]:
        """
        Compress context to fit within token limit.

        Args:
            context_parts: Context parts to compress
            target_tokens: Target token count
            model: Model for token counting

        Returns:
            Compressed context parts
        """
        compressed = []
        current_tokens = 0

        # Priority order: system_prompt, summary, preferences, goals, messages
        priority_order = [
            "system_prompt",
            "conversation_summary",
            "user_preferences",
            "current_goals",
            "relevant_history",
            "recent_messages",
        ]

        for part_type in priority_order:
            part = next((p for p in context_parts if p["type"] == part_type), None)
            if not part:
                continue

            content = part["content"]
            if part_type == "recent_messages" and isinstance(content, list):
                # For messages, apply more aggressive sliding window
                token_budget = target_tokens - current_tokens
                compressed_messages = self._compress_messages(content, token_budget, model)
                part["content"] = compressed_messages
                current_tokens += sum(
                    self.estimate_tokens(msg.get("content", ""), model) for msg in compressed_messages
                )
            else:
                # For other content, truncate if needed
                content_tokens = self.estimate_tokens(str(content), model)
                if current_tokens + content_tokens > target_tokens:
                    # Truncate to fit
                    try:
                        from src.services.agents.token_counter import TokenCounter

                        part["content"] = TokenCounter.truncate_to_tokens(
                            str(content), target_tokens - current_tokens, model
                        )
                    except ImportError:
                        max_chars = (target_tokens - current_tokens) * 4
                        part["content"] = str(content)[:max_chars] + "..."
                    current_tokens = target_tokens
                else:
                    current_tokens += content_tokens

            compressed.append(part)

            if current_tokens >= target_tokens:
                break

        logger.info(f"Context compressed to {current_tokens} tokens (target: {target_tokens})")
        return compressed

    def _compress_messages(
        self, messages: list[dict[str, str]], token_budget: int, model: str = "gpt-4"
    ) -> list[dict[str, str]]:
        """
        Compress messages to fit within token budget.

        Args:
            messages: Messages to compress
            token_budget: Available token budget
            model: Model for token counting

        Returns:
            Compressed messages
        """
        # Start from most recent and work backwards
        compressed = []
        current_tokens = 0

        for msg in reversed(messages):
            msg_tokens = self.estimate_tokens(msg.get("content", ""), model)
            if current_tokens + msg_tokens <= token_budget:
                compressed.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break

        logger.info(f"Compressed messages: {len(compressed)}/{len(messages)} ({current_tokens} tokens)")
        return compressed

    def add_to_short_term(self, content: str, item_type: str = "context", metadata: dict | None = None) -> None:
        """
        Add content to short-term memory (recent context, current turn info).

        Args:
            content: Content to store
            item_type: Type of context (e.g., 'tool_result', 'user_note')
            metadata: Additional metadata
        """
        self.add_context(content, MemoryPriority.SHORT_TERM, item_type, metadata)

    def add_to_medium_term(
        self, content: str, item_type: str = "session_context", metadata: dict | None = None
    ) -> None:
        """
        Add content to medium-term memory (session-level context).

        Args:
            content: Content to store
            item_type: Type of context (e.g., 'decision', 'important_fact')
            metadata: Additional metadata
        """
        self.add_context(content, MemoryPriority.MEDIUM_TERM, item_type, metadata)

    def add_to_permanent(self, content: str, item_type: str = "preference", metadata: dict | None = None) -> None:
        """
        Add content to permanent memory (always retained).

        Args:
            content: Content to store
            item_type: Type of context (e.g., 'preference', 'goal', 'identity')
            metadata: Additional metadata
        """
        self.add_context(content, MemoryPriority.PERMANENT, item_type, metadata)

    def clear_short_term(self) -> None:
        """Clear short-term memory."""
        self.short_term_context.clear()
        logger.info("Short-term memory cleared")

    def clear_medium_term(self) -> None:
        """Clear medium-term memory."""
        self.medium_term_context.clear()
        logger.info("Medium-term memory cleared")

    def clear_all(self) -> None:
        """Clear all memory (except permanent)."""
        self.clear_short_term()
        self.clear_medium_term()
        self._incremental_state = IncrementalContextState()
        logger.info("All non-permanent memory cleared")

    def clear_permanent(self) -> None:
        """Clear permanent memory (use with caution)."""
        self.permanent_context.clear()
        logger.info("Permanent memory cleared")

    def reset_incremental_state(self) -> None:
        """Reset incremental context state."""
        self._incremental_state = IncrementalContextState()
        logger.info("Incremental context state reset")

    def get_stats(self) -> dict[str, Any]:
        """
        Get context manager statistics.

        Returns:
            Dict with memory statistics
        """
        return {
            "permanent_items": len(self.permanent_context),
            "medium_term_items": len(self.medium_term_context),
            "short_term_items": len(self.short_term_context),
            "total_items": (len(self.permanent_context) + len(self.medium_term_context) + len(self.short_term_context)),
            "permanent_tokens": sum(item.token_count for item in self.permanent_context),
            "medium_term_tokens": sum(item.token_count for item in self.medium_term_context),
            "short_term_tokens": sum(item.token_count for item in self.short_term_context),
            "strategy": self.config.strategy.value,
            "max_tokens": self.config.max_tokens,
            "auto_summarize_enabled": self.config.auto_summarize,
            "incremental_state": {
                "conversation_id": self._incremental_state.conversation_id,
                "last_message_count": self._incremental_state.last_message_count,
                "last_token_count": self._incremental_state.last_token_count,
                "has_cached_context": self._incremental_state.cached_context is not None,
            },
        }
