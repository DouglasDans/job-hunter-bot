from src.models import Job, Profile
from src.scorer import score_job, score_jobs

PROFILE = Profile(
    keywords=["React developer"],
    location="Brazil",
    stack_groups=[["React", "Angular"], ["Node.js", "Java", ".NET"]],
    bonus_stack=["PostgreSQL", "Docker"],
    seniority=["Pleno", "Junior"],
    modality=["Remoto", "Híbrido"],
    dealbreakers=["PHP", "Delphi"],
    score_threshold=5.0,
    hours_old=24,
)


def make_job(
    description: str = "",
    title: str = "Software Engineer",
    location: str = "",
    is_remote: bool | None = None,
    job_level: str | None = None,
) -> Job:
    return Job(
        title=title,
        company="Acme",
        url="https://example.com/1",
        source="indeed",
        description=description,
        location=location,
        is_remote=is_remote,
        job_level=job_level,
    )


# --- stack groups scoring -----------------------------------------------

def test_both_groups_matched_scores_seven():
    result = score_job(make_job("We use React and Node.js in our stack."), PROFILE)
    assert result is not None
    assert result.score == 7.0
    assert sorted(result.stack_hits) == ["Node.js", "React"]


def test_one_group_matched_scores_half_required():
    profile = PROFILE.model_copy(update={"score_threshold": 0.0})
    result = score_job(make_job("We use React for our frontend. Backend is Go."), profile)
    assert result is not None
    assert result.score == 3.5
    assert result.stack_hits == ["React"]


def test_any_tech_in_group_counts_as_group_match():
    result = score_job(make_job("We use Angular and Java."), PROFILE)
    assert result is not None
    assert result.score == 7.0


def test_bonus_hits_added_on_top():
    result = score_job(make_job("React Node.js PostgreSQL Docker stack."), PROFILE)
    assert result is not None
    assert result.score == 10.0
    assert sorted(result.bonus_hits) == ["Docker", "PostgreSQL"]


def test_word_boundary_java_does_not_match_javascript():
    profile = PROFILE.model_copy(update={"stack_groups": [["Java"]], "score_threshold": 0.0})
    result = score_job(make_job("We use JavaScript daily, no Java here."), profile)
    assert result is not None
    assert result.stack_hits == ["Java"]
    result_js_only = score_job(make_job("We use JavaScript daily."), profile)
    assert result_js_only.stack_hits == []
    assert result_js_only.score == 0.0


def test_bonus_stack_is_word_boundary_aware():
    profile = PROFILE.model_copy(update={"bonus_stack": ["Java"]})
    result = score_job(make_job("React Node.js, and JavaScript on the frontend."), profile)
    assert result is not None
    assert result.bonus_hits == []


def test_case_insensitive():
    result = score_job(make_job("Experience with REACT and NODE.JS required."), PROFILE)
    assert result is not None
    assert "React" in result.stack_hits
    assert "Node.js" in result.stack_hits


def test_node_synonym_variants_all_match():
    for variant in ("Node.js", "nodejs", "node"):
        profile = PROFILE.model_copy(update={"stack_groups": [["Node.js"]], "score_threshold": 0.0})
        result = score_job(make_job(f"Backend built with {variant}."), profile)
        assert result.stack_hits == ["Node.js"], variant


def test_dotnet_synonym_variants_all_match():
    for variant in (".NET", "dotnet", "ASP.NET"):
        profile = PROFILE.model_copy(update={"stack_groups": [[".NET"]], "score_threshold": 0.0})
        result = score_job(make_job(f"Backend built with {variant}."), profile)
        assert result.stack_hits == [".NET"], variant


def test_csharp_synonym_variants_all_match():
    for variant in ("C#", "csharp"):
        profile = PROFILE.model_copy(update={"stack_groups": [["C#"]], "score_threshold": 0.0})
        result = score_job(make_job(f"Backend built with {variant}."), profile)
        assert result.stack_hits == ["C#"], variant


# --- dealbreakers ---------------------------------------------------------

def test_generic_dealbreaker_vetoes():
    result = score_job(make_job("We use PHP and React."), PROFILE)
    assert result is None


def test_generic_dealbreaker_in_title_vetoes():
    result = score_job(make_job(title="PHP Developer", description="React is used too."), PROFILE)
    assert result is None


def test_generic_dealbreaker_word_boundary():
    profile = PROFILE.model_copy(update={"dealbreakers": ["PHP"]})
    result = score_job(make_job("We use PHPStorm as our IDE, stack is React and Node.js."), profile)
    assert result is not None


def test_modality_dealbreaker_ignores_description_body():
    profile = PROFILE.model_copy(update={"dealbreakers": ["trabalho presencial"]})
    job = make_job(
        "React Node.js. Benefícios: auxílio mobilidade (trabalho híbrido ou presencial).",
        title="Dev Fullstack (Remoto)",
    )
    result = score_job(job, profile)
    assert result is not None


def test_modality_dealbreaker_vetoes_via_title():
    profile = PROFILE.model_copy(update={"dealbreakers": ["presencial"]})
    job = make_job("React Node.js.", title="Desenvolvedor Presencial")
    result = score_job(job, profile)
    assert result is None


# --- modality veto (unified) ----------------------------------------------

def test_is_remote_true_passes():
    job = make_job("React Node.js", title="React Dev", is_remote=True)
    assert score_job(job, PROFILE) is not None


def test_is_remote_none_passes():
    job = make_job("React Node.js", title="React Dev", is_remote=None)
    assert score_job(job, PROFILE) is not None


def test_is_remote_false_vetoes_when_profile_is_remoto_only():
    profile = PROFILE.model_copy(update={"modality": ["Remoto"]})
    job = make_job("React Node.js", title="React Dev", is_remote=False)
    assert score_job(job, profile) is None


def test_is_remote_false_passes_when_profile_accepts_hibrido():
    job = make_job("React Node.js", title="React Dev", is_remote=False)
    assert score_job(job, PROFILE) is not None


def test_hybrid_title_bypasses_modality_veto_even_if_remoto_only_profile():
    profile = PROFILE.model_copy(update={"modality": ["Remoto"]})
    job = make_job("React Node.js", title="Dev Fullstack Híbrido", is_remote=False)
    assert score_job(job, profile) is not None


def test_modality_term_in_description_alone_does_not_veto():
    profile = PROFILE.model_copy(update={"dealbreakers": ["presencial"]})
    job = make_job(
        "React Node.js. Trabalho presencial nas visitas ao cliente ocasionalmente.",
        title="Dev Fullstack",
        is_remote=None,
    )
    result = score_job(job, profile)
    assert result is not None


# --- seniority --------------------------------------------------------------

def test_senior_title_vetoed_when_not_in_seniority():
    job = make_job("React Node.js", title="Senior React Developer")
    assert score_job(job, PROFILE) is None


def test_senior_with_accent_vetoed():
    job = make_job("React Node.js", title="Desenvolvedor React Sênior")
    assert score_job(job, PROFILE) is None


def test_sr_token_vetoed():
    job = make_job("React Node.js", title="Dev React Sr.")
    assert score_job(job, PROFILE) is None


def test_sre_title_not_vetoed():
    job = make_job("React Node.js", title="React SRE")
    assert score_job(job, PROFILE) is not None


def test_iii_token_vetoed():
    job = make_job("React Node.js", title="Engenheiro de Software III")
    assert score_job(job, PROFILE) is None


def test_especialista_token_vetoed():
    job = make_job("React Node.js", title="Desenvolvedor Especialista React")
    assert score_job(job, PROFILE) is None


def test_staff_token_vetoed():
    job = make_job("React Node.js", title="Staff Engineer")
    assert score_job(job, PROFILE) is None


def test_lead_token_vetoed():
    job = make_job("React Node.js", title="Lead Developer")
    assert score_job(job, PROFILE) is None


def test_principal_token_vetoed():
    job = make_job("React Node.js", title="Principal Engineer")
    assert score_job(job, PROFILE) is None


def test_senior_job_level_vetoed():
    job = make_job("React Node.js", job_level="senior")
    assert score_job(job, PROFILE) is None


def test_mid_senior_job_level_vetoed():
    job = make_job("React Node.js", job_level="mid-senior level")
    assert score_job(job, PROFILE) is None


def test_senior_passes_when_senior_in_profile():
    profile = PROFILE.model_copy(update={"seniority": ["Senior", "Pleno"]})
    job = make_job("React Node.js", title="Senior React Developer")
    assert score_job(job, profile) is not None


def test_senior_passes_when_seniority_empty():
    profile = PROFILE.model_copy(update={"seniority": []})
    job = make_job("React Node.js", title="Senior React Developer")
    assert score_job(job, profile) is not None


def test_non_senior_title_not_vetoed():
    job = make_job("React Node.js", title="Fullstack Software Engineer Pleno")
    assert score_job(job, PROFILE) is not None


def test_pl_sql_gives_positive_signal_but_is_not_vetoed():
    job = make_job("React Node.js", title="PL/SQL Developer")
    result = score_job(job, PROFILE)
    assert result is not None
    assert result.seniority_signal == "Pleno"


def test_veto_wins_over_positive_signal():
    job = make_job("React Node.js", title="Desenvolvedor Pleno Especialista")
    assert score_job(job, PROFILE) is None


def test_seniority_signal_pleno():
    job = make_job("React Node.js", title="Desenvolvedor Pleno")
    result = score_job(job, PROFILE)
    assert result.seniority_signal == "Pleno"


def test_seniority_signal_junior():
    job = make_job("React Node.js", title="Desenvolvedor Júnior")
    result = score_job(job, PROFILE)
    assert result.seniority_signal == "Junior"


def test_seniority_signal_none_when_no_token():
    job = make_job("React Node.js", title="Fullstack Software Engineer")
    result = score_job(job, PROFILE)
    assert result.seniority_signal is None


# --- score_jobs / below threshold ------------------------------------------

def test_below_threshold_returns_none():
    result = score_job(make_job("Pure Go shop, no matching stack."), PROFILE)
    assert result is None


def test_score_jobs_filters_nones_and_sorts():
    jobs = [
        make_job("React Node.js PostgreSQL Docker"),  # 10.0
        make_job("PHP developer"),  # dealbreaker -> None
        make_job("Pure Go shop"),  # 0.0 < threshold -> None
        make_job("React Node.js Docker"),  # 8.5
    ]
    results = score_jobs(jobs, PROFILE)
    assert len(results) == 2
    assert results[0].score == 10.0
    assert results[1].score == 8.5


def test_score_jobs_empty_input():
    assert score_jobs([], PROFILE) == []


# --- acceptance case: Venturus [1277] --------------------------------------

def test_acceptance_venturus_fullstack_dotnet_react_job():
    profile = Profile(
        keywords=["desenvolvedor fullstack"],
        location="Brazil",
        stack_groups=[
            ["React", "Angular", "Next.js"],
            ["Node.js", "NestJS", "Express", "Java", "Spring", ".NET", "C#"],
        ],
        bonus_stack=["PostgreSQL", "Docker", "AWS"],
        seniority=["Pleno", "Junior"],
        modality=["Remoto", "Híbrido"],
        dealbreakers=["PHP", "Delphi", "trabalho presencial"],
        score_threshold=6.0,
        hours_old=24,
    )
    job = make_job(
        title="[1277] Pessoa Desenvolvedora Fullstack (.Net C# / React) Pl (Remoto)",
        description=(
            "Buscamos pessoa desenvolvedora fullstack com experiência em .NET C# e React."
            " Benefícios: auxílio mobilidade (trabalho híbrido ou presencial)."
        ),
    )
    result = score_job(job, profile)
    assert result is not None
    assert result.score >= 7.0
    assert result.seniority_signal == "Pleno"
