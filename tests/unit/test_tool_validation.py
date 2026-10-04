from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app.schemas.tools import ToolArgs
from app.mcp.router import server_for
from app.agent.result_validation import validate_result

@pytest.mark.parametrize('arguments', [{'user_id': 'bob'}, {'budget': -1}, {'budget': 1001}, {'spice': 3},
    {'date': '2026-99-99'}, {'query': 'x' * 1001}, {'building': 'A'}])
def test_unsupported_and_out_of_range_arguments_rejected(arguments):
    with pytest.raises(ValidationError): ToolArgs.model_validate(arguments)

def test_parameter_boundaries_are_valid():
    value = ToolArgs.model_validate({'date': '2026-10-04', 'budget': 0, 'spice': 0, 'vegetarian': False})
    assert value.budget == 0 and value.vegetarian is False

def test_registry_does_not_allow_write_tools_even_with_registered_url():
    settings = SimpleNamespace(mcp_servers={'pay': 'http://unused', 'query_classrooms': 'http://local/mcp'})
    assert server_for(settings, 'query_classrooms') == 'http://local/mcp'
    with pytest.raises(ValueError, match='allowlisted'): server_for(settings, 'pay')

@pytest.mark.parametrize('value', [None, {'rows': 'invalid'}, {'rows': [1]}, {'rows': [{}] * 101}])
def test_malformed_or_excessive_tool_results_rejected(value):
    with pytest.raises(ValueError): validate_result(value)

def test_accepted_result_is_capped_at_twenty_rows():
    assert len(validate_result({'rows': [{'id': str(i)} for i in range(21)]})['rows']) == 20
