"""Base types for the multi-provider AI system."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderName(str, Enum):
    MISTRAL     = "mistral"
    ANTHROPIC   = "anthropic"
    OPENAI      = "openai"
    GROQ        = "groq"
    GEMINI      = "gemini"
    OPENROUTER  = "openrouter"
    OLLAMA      = "ollama"
    DICTIONARY  = "dictionary"
    OFFLINE     = "offline"


@dataclass
class VocabResult:
    word:                str
    lemma:               str
    translation:         str
    phonetic:            str
    part_of_speech:      str
    cefr_level:          str
    frequency_rank:      str
    example_sentence:    str
    sentence_translation:str
    is_idiom:            bool = False
    is_slang:            bool = False
    explanation:         str  = ""
    provider:            str  = ""

    def to_dict(self) -> dict:
        return {
            "word":                self.word,
            "lemma":               self.lemma,
            "translation":         self.translation,
            "phonetic":            self.phonetic,
            "partOfSpeech":        self.part_of_speech,
            "cefrLevel":           self.cefr_level,
            "frequencyRank":       self.frequency_rank,
            "exampleSentence":     self.example_sentence,
            "sentenceTranslation": self.sentence_translation,
            "isIdiom":             self.is_idiom,
            "isSlang":             self.is_slang,
            "explanation":         self.explanation,
            "provider":            self.provider,
        }


@dataclass
class TranslationResult:
    translations: list[dict]   # [{index, text}]
    provider:     str = ""


class BaseProvider(ABC):
    name: ProviderName

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def enrich_word(
        self,
        word: str,
        lemma: str,
        context: str,
        source_lang: str,
        target_lang: str,
    ) -> VocabResult: ...

    @abstractmethod
    def translate_batch(
        self,
        blocks: list[dict],
        source_lang: str,
        target_lang: str,
    ) -> TranslationResult: ...
