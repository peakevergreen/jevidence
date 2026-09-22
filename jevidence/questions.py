"""Question definitions owned by the application, never by issue text."""
QUESTION_VERSION = "developer-issue-v1"
MODEL = "jev-1.13.0"


def issue_questions():
    # Import only for live use; the offline sandbox has no dependencies.
    from typesafe_sdk import Choice, Noul, Score

    return {
        "route": Choice(
            instructions="Which area should first investigate this issue?",
            criteria={
                "docs": "Incorrect or missing written instructions.",
                "build": "Installation, compilation, or packaging failure.",
                "runtime": "Unexpected behavior in a running application.",
                "other": "Ambiguous, unrelated, or no listed area fits.",
            },
        ),
        "reproduction": Noul(instructions=(
            "Does the report give an explicit sequence of actions "
            "that a developer could attempt to reproduce the issue?"
        )),
        "specificity": Score(
            instructions="How specific is the reported observation?",
            criteria=[
                "Only a general complaint; no identifiable behavior.",
                "Identifiable behavior, without expected versus actual detail.",
                "A concrete expected result and a concrete actual result.",
            ],
        ),
    }
