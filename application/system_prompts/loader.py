
PATH_SYSTEM_PROMPT = 'prompts/agentic'
PATH2_SYSTEM_PROMPT = 'versions/v1/system_prompts'
PATH3_SYSTEM_PROMPT = 'system_prompts copy'


GENERIC_SYSTEM_PROMPT = PATH_SYSTEM_PROMPT + '/0_generic_prompt.txt'

PHASE1_SYSTEM_PROMPT = PATH_SYSTEM_PROMPT + '/1_triage_specialist.txt'
PHASE2_SYSTEM_PROMPT = PATH_SYSTEM_PROMPT + '/2_project_manager.txt'
PHASE3_SYSTEM_PROMPT = PATH_SYSTEM_PROMPT + '/3_system_architect.txt'
PHASE4_SYSTEM_PROMPT = PATH_SYSTEM_PROMPT + '/4_safety_quality_gatekeeper.txt'
PHASE5_SYSTEM_PROMPT = PATH_SYSTEM_PROMPT + '/5_cognitive_worker.txt'
PHASE6_SYSTEM_PROMPT = PATH_SYSTEM_PROMPT + '/6_mcp_operator.txt'
PHASE7_SYSTEM_PROMPT = PATH_SYSTEM_PROMPT + '/7_data_engineer.txt'
PHASE8_SYSTEM_PROMPT = PATH_SYSTEM_PROMPT + '/8_drawf_writter.txt'
PHASE9_SYSTEM_PROMPT = PATH_SYSTEM_PROMPT + '/9_editor_in_chief.txt'


def load_file(filepath):
    with open(filepath, 'r') as f:
        return f.read()

def LoadSystemPrompt(phase: int) -> str | None:
    if phase == 1:
        return load_file(PHASE1_SYSTEM_PROMPT)
    if phase == 2:
        return load_file(PHASE2_SYSTEM_PROMPT)
    if phase == 3:
        return load_file(PHASE3_SYSTEM_PROMPT)
    if phase == 4:
        return load_file(PHASE4_SYSTEM_PROMPT)
    if phase == 5:
        return load_file(PHASE5_SYSTEM_PROMPT)
    if phase == 6:
        return load_file(PHASE6_SYSTEM_PROMPT)
    if phase == 7:
        return load_file(PHASE7_SYSTEM_PROMPT)
    if phase == 8:
        return load_file(PHASE8_SYSTEM_PROMPT)
    if phase == 9:
        return load_file(PHASE9_SYSTEM_PROMPT)
    if phase == 0:
        return load_file(GENERIC_SYSTEM_PROMPT)

    return None