"""
Run Calculator: Execute arithmetic from graph structure.

Usage:
    python -m lab_executable.run_calc                    # Default: 3 + 5
    python -m lab_executable.run_calc --a 7 --b 2        # Custom: 7 + 2
    python -m lab_executable.run_calc --graph calc.json  # From file
"""

import argparse
import json
import sys
from pathlib import Path

from .executor import GraphExecutor, create_addition_graph


def run_from_graph(graph_data: dict, verbose: bool = True) -> int:
    """Execute calculation from graph and return result."""
    executor = GraphExecutor(graph_data=graph_data)
    
    if verbose:
        print("\n" + "=" * 50)
        print("  GRAPH-EXECUTABLE CALCULATOR")
        print("  (Computation defined by graph structure)")
        print("=" * 50)
        
        # Show the graph
        print("\nGraph Structure:")
        print("-" * 50)
        for node in graph_data['nodes']:
            node_type = node['type']
            node_id = node['id']
            if node_type == 'OPERAND':
                value = node['data']['value']
                print(f"  [{node_type}] {node_id} = {value}")
            elif node_type == 'OPERATION':
                op = node['data']['operation']
                print(f"  [{node_type}] {node_id} ({op})")
            else:
                print(f"  [{node_type}] {node_id}")
        
        print()
        for edge in graph_data['edges']:
            print(f"  {edge['from_id']} --{edge['relation']}--> {edge['to_id']}")
    
    # Execute
    trace = executor.execute('result')
    
    if verbose:
        trace.print_trace()
        print(f"✅ Graph computed: {trace.final_result}")
    
    return trace.final_result


def main():
    parser = argparse.ArgumentParser(
        description="Execute arithmetic from graph structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m lab_executable.run_calc              # 3 + 5 = 8
    python -m lab_executable.run_calc --a 10 --b 20  # 10 + 20 = 30
    python -m lab_executable.run_calc --graph my_calc.json

The key insight: The Python code doesn't know what numbers to add.
The GRAPH contains the values. Change the graph, change the result.

This proves: Graph IS the program.
        """
    )
    
    parser.add_argument('--a', type=int, default=3,
                        help='First operand (default: 3)')
    parser.add_argument('--b', type=int, default=5,
                        help='Second operand (default: 5)')
    parser.add_argument('--graph', type=str,
                        help='Load graph from JSON file instead of generating')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Only output the result')
    
    args = parser.parse_args()
    
    # Load or create graph
    if args.graph:
        with open(args.graph, 'r') as f:
            graph_data = json.load(f)
    else:
        graph_data = create_addition_graph(args.a, args.b)
    
    # Save the graph for inspection
    state_dir = Path(__file__).parent / 'state'
    state_dir.mkdir(exist_ok=True)
    with open(state_dir / 'calculation.json', 'w') as f:
        json.dump(graph_data, f, indent=2)
    
    # Execute
    result = run_from_graph(graph_data, verbose=not args.quiet)
    
    if args.quiet:
        print(result)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
