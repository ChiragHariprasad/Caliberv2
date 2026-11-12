"""CALIBRE SIA Core v3 - deterministic decision-scoped integrity engine."""
from .algebra import IntegrityState, Timeline, and_state, or_state, k_of_n_state
from .calibration import estimate_bias
from .canon import fmt_instant, jcs, parse_instant, sec_to_us, sha256_hex
from .contract import Contract, ContractError, load_contract_file, load_contract_yaml, parse_contract, validate_contract
from .engine import ContractRejected, IntegrityEngine
from .evaluator import EngineConfig
from .model import (EvidenceAtom, GuardFact, OriginRegistry, ReferenceFact, ScopeClass, make_atom, make_fact, make_guard)
from .timeclass import TimeClass, TypedTime
from .verdict import Assessment, explain, verify_chain

__version__ = "3.0.0"
