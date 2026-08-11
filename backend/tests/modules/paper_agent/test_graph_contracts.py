import unittest

from pydantic import BaseModel, ConfigDict, ValidationError

from app.modules.paper_agent.graph import (
    INITIALIZE_NODE_CONTRACT,
    GraphNodeContract,
    InitializeNodeInput,
    InitializeNodeOutput,
    MAIN_WORKFLOW_NODES,
    PaperGraphExecution,
    PaperGraphState,
    add_contract_node,
    get_node_contract,
    initialize_paper_agent,
    validated_node,
)
from app.modules.paper_agent.schemas import PaperJobStatus


class SelectionNodeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_question_ids: list[str]


class FakeGraph:
    def __init__(self):
        self.nodes: dict[str, object] = {}
        self.input_schemas: dict[str, type[BaseModel]] = {}

    def add_node(
        self,
        name: str,
        node: object,
        *,
        input_schema: type[BaseModel],
    ) -> None:
        self.nodes[name] = node
        self.input_schemas[name] = input_schema


class GraphNodeContractTests(unittest.TestCase):
    def test_initialize_node_declares_pydantic_contract(self):
        contract = get_node_contract(initialize_paper_agent)

        self.assertIs(contract, INITIALIZE_NODE_CONTRACT)
        self.assertTrue(issubclass(contract.input_model, BaseModel))
        self.assertTrue(issubclass(contract.output_model, BaseModel))
        self.assertIs(contract.input_model, InitializeNodeInput)
        self.assertIs(contract.output_model, InitializeNodeOutput)
        self.assertEqual(
            set(InitializeNodeInput.model_fields),
            {
                "job_id",
                "candidate_question_ids",
                "selected_question_ids",
                "reports",
                "execution",
            },
        )
        self.assertNotIn("paper_id", InitializeNodeInput.model_fields)

    def test_contract_requires_pydantic_models(self):
        with self.assertRaises(TypeError):
            GraphNodeContract(
                name="invalid-model",
                state_model=PaperGraphState,
                input_model=dict,
                output_model=InitializeNodeOutput,
            )

    def test_initialize_node_validates_input_and_output(self):
        update = initialize_paper_agent(PaperGraphState(job_id="job-013"))
        output = InitializeNodeOutput.model_validate(update)

        self.assertEqual(output.execution.status, PaperJobStatus.RUNNING)
        self.assertEqual(output.reports[0].stage, "initialize")

        with self.assertRaises(ValidationError):
            initialize_paper_agent(
                {
                    "job_id": "job-rich-input",
                    "question": {"id": "question-1", "stem": "Payload"},
                }
            )

    def test_contract_rejects_invalid_node_output(self):
        contract = GraphNodeContract(
            name="invalid-output",
            state_model=PaperGraphState,
            input_model=PaperGraphState,
            output_model=InitializeNodeOutput,
        )

        @validated_node(contract)
        def invalid_output(_: PaperGraphState) -> dict:
            return {"reports": []}

        with self.assertRaises(ValidationError):
            invalid_output(PaperGraphState(job_id="job-invalid-output"))

    def test_contract_validates_merged_graph_state(self):
        contract = GraphNodeContract(
            name="invalid-selection",
            state_model=PaperGraphState,
            input_model=PaperGraphState,
            output_model=SelectionNodeOutput,
        )

        @validated_node(contract)
        def invalid_selection(_: PaperGraphState) -> SelectionNodeOutput:
            return SelectionNodeOutput(selected_question_ids=["missing-question"])

        with self.assertRaises(ValidationError):
            invalid_selection(PaperGraphState(job_id="job-invalid-selection"))

    def test_failed_output_must_follow_execution_contract(self):
        with self.assertRaises(ValidationError):
            InitializeNodeOutput(
                reports=[],
                execution={"status": PaperJobStatus.FAILED},
            )

        output = InitializeNodeOutput(
            reports=[],
            execution=PaperGraphExecution(
                status=PaperJobStatus.FAILED,
                current_node="initialize",
                error_code="INITIALIZE_FAILED",
            ),
        )
        self.assertEqual(output.execution.error_code, "INITIALIZE_FAILED")

    def test_graph_registration_rejects_node_without_contract(self):
        graph = FakeGraph()

        with self.assertRaises(TypeError):
            add_contract_node(graph, lambda state: state)

        node_name = add_contract_node(graph, initialize_paper_agent)
        self.assertEqual(node_name, "initialize")
        self.assertIn("initialize", graph.nodes)
        self.assertIs(graph.input_schemas["initialize"], PaperGraphState)

    def test_all_main_workflow_nodes_declare_unique_pydantic_contracts(self):
        contracts = [get_node_contract(node) for node in MAIN_WORKFLOW_NODES]

        self.assertEqual(len(contracts), 5)
        self.assertEqual(len({contract.name for contract in contracts}), 5)
        for contract in contracts:
            self.assertTrue(issubclass(contract.input_model, BaseModel))
            self.assertTrue(issubclass(contract.output_model, BaseModel))


class AsyncGraphNodeContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_node_uses_the_same_contract_validation(self):
        contract = GraphNodeContract(
            name="async-initialize",
            state_model=PaperGraphState,
            input_model=PaperGraphState,
            output_model=InitializeNodeOutput,
        )

        @validated_node(contract)
        async def async_node(_: PaperGraphState) -> InitializeNodeOutput:
            return InitializeNodeOutput(
                reports=[],
                execution=PaperGraphExecution(
                    status=PaperJobStatus.RUNNING,
                    current_node="async-initialize",
                    attempt=1,
                ),
            )

        update = await async_node(PaperGraphState(job_id="job-async-contract"))
        output = InitializeNodeOutput.model_validate(update)
        self.assertEqual(output.execution.current_node, "async-initialize")


if __name__ == "__main__":
    unittest.main()
