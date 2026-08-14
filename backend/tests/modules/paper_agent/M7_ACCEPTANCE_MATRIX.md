# M7 Conversational Paper Agent Acceptance Matrix

| # | Scenario | Automated coverage | Required result |
|---|---|---|---|
| 01 | Complete structured request | `test_plan_parser.PaperPlanParserTests.test_maps_names_to_real_codes_and_calculates_totals` | Produces a validated `PaperPlan` with real taxonomy codes. |
| 02 | Multi-turn partial update | `test_plan_parser.PaperPlanParserTests.test_second_turn_preserves_omitted_previous_fields` | Changes only explicit fields and keeps the previous plan. |
| 03 | Missing required parameters | `test_m7_acceptance.M7AcceptanceScenarios.test_03_missing_fields_request_clarification` | Asks for module, knowledge point, and quota; creates no plan. |
| 04 | Unknown or fabricated taxonomy | `test_plan_parser.PaperPlanParserTests.test_unknown_taxonomy_label_never_enters_plan` | Rejects unknown labels and never invents a code. |
| 05 | Conflicting totals | `test_plan_parser.PaperPlanParserTests.test_conflicting_question_count_and_score_require_clarification` | Asks which total is authoritative and does not auto-relax. |
| 06 | Infeasible question bank | `test_m7_acceptance.M7AcceptanceScenarios.test_06_infeasible_plan_finishes_without_confirmation` | Returns `infeasible`; no interrupt and no execution. |
| 07 | Confirmation gate | `test_conversation_workflow.ConversationWorkflowTests.test_complete_plan_interrupts_before_any_execution` | Persists one pending action and pauses before all writes. |
| 08 | Teacher cancellation | `test_conversation_workflow.ConversationWorkflowTests.test_cancel_never_executes` | Ends as cancelled with zero tool executions. |
| 09 | Confirmed execution | `test_conversation_workflow.ConversationWorkflowTests.test_confirm_executes_once_and_completes` | Executes exactly once and links one `PaperJob`. |
| 10 | Duplicate action or command | `test_conversation_tools.ConversationToolTests.test_completed_action_id_returns_saved_result_without_reexecution`; `test_conversation_api.ConversationApiTests.test_repeated_command_returns_uniform_conflict` | Returns saved result or 409 without a second write. |
| 11 | Failure, retry, timeout | `test_conversation_workflow.ConversationWorkflowTests.test_failed_execution_creates_new_confirmation_before_retry`; `test_conversation_tools.ConversationToolTests.test_read_tool_retries_one_transient_timeout`; `test_conversation_tools.ConversationToolTests.test_write_tool_never_retries_automatically` | Read tools retry once; writes require a new confirmed action. |
| 12 | Restart, injection, and fallback | `test_conversation_checkpoint.PostgreSQLConversationCheckpointTests.test_confirmation_resumes_after_runtime_recreation`; `test_m7_acceptance.M7AcceptanceScenarios.test_12_prompt_injection_cannot_add_tools_or_taxonomy`; frontend production build and browser regression | PostgreSQL restores interrupts; dangerous tools and invented labels remain blocked; the M6 form remains available. |

Run the backend matrix with:

```bash
python -W error -m unittest discover -s tests -p "test_*.py"
```

Run the frontend regression with:

```bash
npm run build
```
