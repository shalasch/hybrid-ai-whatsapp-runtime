from typing import Literal

RoutingAction = Literal[
    "ask_name",
    "capture_name",
    "send_menu",
    "send_quiz",
    "human_wait",
    "ask_goal",
    "answer_faq",
    "route_payload_offshore_interview",
    "route_payload_professional_english",
    "route_payload_general_english",
    "route_payload_trial_class",
    "route_payload_student_support",
    "route_payload_human_support",
]

ALLOWED_ROUTING_ACTIONS: set[str] = set(RoutingAction.__args__)  # type: ignore[attr-defined]
