"""
Simulate cost spikes to test SentinelLLM cost monitoring and alerting
"""
import requests
import time
import logging
from typing import List, Dict, Optional
import json
import random


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CostSpikeSimulator:
    """Simulate various cost spike scenarios for testing"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.scenarios = self._load_cost_scenarios()
    
    def _load_cost_scenarios(self) -> List[Dict]:
        """Load various cost spike scenarios"""
        scenarios = [
            {
                "name": "Normal Usage",
                "description": "Regular, moderate usage",
                "requests": 5,
                "tokens_per_request": {"min": 50, "max": 200},
                "expected_cost_impact": "low"
            },
            {
                "name": "Token Explosion",
                "description": "Requests with extremely high token counts",
                "requests": 3,
                "tokens_per_request": {"min": 2000, "max": 5000},
                "expected_cost_impact": "high"
            },
            {
                "name": "High Volume Burst",
                "description": "Many short requests that accumulate cost",
                "requests": 50,
                "tokens_per_request": {"min": 10, "max": 100},
                "expected_cost_impact": "medium"
            },
            {
                "name": "Premium Model Usage",
                "description": "Using more expensive models",
                "requests": 10,
                "tokens_per_request": {"min": 100, "max": 500},
                "expected_cost_impact": "medium"
            },
            {
                "name": "Massive Single Request",
                "description": "One very large request",
                "requests": 1,
                "tokens_per_request": {"min": 8000, "max": 10000},
                "expected_cost_impact": "very_high"
            },
            {
                "name": "Aggressive Rate Limiting Bypass",
                "description": "Rapid requests to bypass rate limits",
                "requests": 20,
                "tokens_per_request": {"min": 500, "max": 1500},
                "expected_cost_impact": "high"
            }
        ]
        return scenarios
    
    def run_simulation(self, delay: float = 1.0) -> Dict:
        """Run all cost spike scenarios and collect results"""
        logger.info("Starting cost spike simulation...")
        
        results = {
            "total_scenarios": len(self.scenarios),
            "total_requests": 0,
            "total_tokens": 0,
            "estimated_total_cost": 0.0,
            "scenario_results": [],
            "cost_distribution": {
                "low": 0,
                "medium": 0,
                "high": 0,
                "very_high": 0
            }
        }
        
        for scenario in self.scenarios:
            try:
                logger.info(f"Running scenario: {scenario['name']}")
                
                scenario_result = self._run_scenario(scenario)
                results["scenario_results"].append(scenario_result)
                results["total_requests"] += scenario_result["requests_made"]
                results["total_tokens"] += scenario_result["total_tokens"]
                results["estimated_total_cost"] += scenario_result["estimated_cost"]
                
                # Update cost distribution
                impact = scenario["expected_cost_impact"]
                results["cost_distribution"][impact] += 1
                
                # Delay between scenarios
                time.sleep(delay * 2)
                
            except Exception as e:
                logger.error(f"Error in scenario {scenario['name']}: {e}")
                results["scenario_results"].append({
                    "name": scenario["name"],
                    "error": str(e),
                    "success": False
                })
        
        return results
    
    def _run_scenario(self, scenario: Dict) -> Dict:
        """Run a specific cost scenario"""
        start_time = time.time()
        scenario_tokens = 0
        scenario_cost = 0.0
        successful_requests = 0
        failed_requests = 0
        request_details = []
        
        for i in range(scenario["requests"]):
            try:
                # Generate a large prompt to simulate high token usage
                prompt = self._generate_large_prompt(
                    scenario["tokens_per_request"]["min"],
                    scenario["tokens_per_request"]["max"]
                )
                
                # Send request
                response = self._send_request(prompt, max_tokens=1000)
                
                if response.get("status_code") == 200:
                    successful_requests += 1
                    response_data = response.get("response_data", {})
                    
                    # Track tokens and costs
                    input_tokens = response_data.get("input_tokens", 0)
                    output_tokens = response_data.get("output_tokens", 0)
                    request_cost = response_data.get("cost_estimate", 0.0)
                    
                    scenario_tokens += input_tokens + output_tokens
                    scenario_cost += request_cost
                    
                    request_details.append({
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost": request_cost,
                        "success": True
                    })
                    
                else:
                    failed_requests += 1
                    request_details.append({
                        "error": response.get("error", "Unknown error"),
                        "success": False
                    })
                
                # Small delay between requests
                time.sleep(0.1)
                
            except Exception as e:
                failed_requests += 1
                request_details.append({
                    "error": str(e),
                    "success": False
                })
        
        end_time = time.time()
        
        return {
            "name": scenario["name"],
            "description": scenario["description"],
            "expected_cost_impact": scenario["expected_cost_impact"],
            "requests_planned": scenario["requests"],
            "requests_made": successful_requests + failed_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "total_tokens": scenario_tokens,
            "estimated_cost": scenario_cost,
            "duration_seconds": end_time - start_time,
            "cost_per_request": scenario_cost / max(1, successful_requests),
            "tokens_per_request": scenario_tokens / max(1, successful_requests),
            "request_details": request_details[:5],  # Keep only first 5 for brevity
            "success": True
        }
    
    def _generate_large_prompt(self, min_tokens: int, max_tokens: int) -> str:
        """Generate a large prompt to simulate high token usage"""
        target_tokens = random.randint(min_tokens, max_tokens)
        
        # Template for generating large content
        templates = [
            "Write a comprehensive analysis of",
            "Provide detailed information about",
            "Create a detailed report on",
            "Explain in depth the concept of",
            "Develop a thorough discussion about",
            "Generate a complete guide to",
            "Compose a detailed explanation of",
            "Formulate a comprehensive overview of"
        ]
        
        topics = [
            "artificial intelligence and machine learning",
            "climate change and environmental impact",
            "quantum computing and its applications",
            "cybersecurity and digital privacy",
            "blockchain technology and cryptocurrency",
            "renewable energy and sustainability",
            "space exploration and colonization",
            "genetic engineering and biotechnology"
        ]
        
        # Start with a template and topic
        prompt = f"{random.choice(templates)} {random.choice(topics)}.\n\n"
        
        # Add content to reach target token count
        while len(prompt.split()) < target_tokens // 1.3:  # Rough estimate: 1.3 tokens per word
            additional_content = [
                f"Include historical context, current developments, and future implications. Consider multiple perspectives and provide examples from various industries and use cases.",
                f"Analyze the technical specifications, economic factors, regulatory considerations, and social implications. Discuss potential benefits and challenges.",
                f"Examine case studies, best practices, and emerging trends. Compare different approaches and methodologies used in this field.",
                f"Evaluate the impact on society, business, and technology. Discuss scalability, implementation challenges, and potential solutions.",
                f"Provide recommendations for stakeholders, policymakers, and practitioners. Include actionable insights and strategic considerations."
            ]
            prompt += f"{random.choice(additional_content)}\n\n"
        
        return prompt
    
    def _send_request(self, prompt: str, max_tokens: int = 1000) -> Dict:
        """Send a request to the SentinelLLM API"""
        try:
            url = f"{self.base_url}/api/v1/generate"
            data = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": 0.7
            }
            
            response = requests.post(url, json=data, timeout=60)
            
            result = {
                "status_code": response.status_code,
                "response_data": None,
                "error": None
            }
            
            if response.status_code == 200:
                result["response_data"] = response.json()
            else:
                result["error"] = response.text
            
            return result
            
        except requests.RequestException as e:
            return {
                "status_code": 0,
                "response_data": None,
                "error": f"Request failed: {str(e)}"
            }
    
    def print_summary(self, results: Dict):
        """Print a summary of the cost simulation results"""
        print("\n" + "="*80)
        print("COST SPIKE SIMULATION RESULTS")
        print("="*80)
        
        print(f"Total Scenarios: {results['total_scenarios']}")
        print(f"Total Requests: {results['total_requests']}")
        print(f"Total Tokens Processed: {results['total_tokens']:,}")
        print(f"Estimated Total Cost: ${results['estimated_total_cost']:.6f}")
        
        print(f"\nCost Distribution by Scenario:")
        for impact, count in results["cost_distribution"].items():
            print(f"  {impact.replace('_', ' ').title()}: {count} scenarios")
        
        print(f"\nDetailed Scenario Results:")
        for scenario in results["scenario_results"]:
            if scenario.get("success", False):
                print(f"  {scenario['name']}:")
                print(f"    Requests: {scenario['successful_requests']}/{scenario['requests_made']}")
                print(f"    Tokens: {scenario['total_tokens']:,}")
                print(f"    Cost: ${scenario['estimated_cost']:.6f}")
                print(f"    Cost/Request: ${scenario['cost_per_request']:.6f}")
                print(f"    Duration: {scenario['duration_seconds']:.1f}s")
            else:
                print(f"  {scenario['name']}: FAILED - {scenario.get('error', 'Unknown error')}")
        
        # Check if any scenarios would trigger cost alerts
        high_cost_scenarios = [s for s in results["scenario_results"] 
                             if s.get("estimated_cost", 0) > 0.1]  # Threshold for demo
        if high_cost_scenarios:
            print(f"\n⚠️  {len(high_cost_scenarios)} scenarios would trigger cost alerts:")
            for scenario in high_cost_scenarios:
                print(f"    {scenario['name']}: ${scenario['estimated_cost']:.6f}")
        
        print("\n" + "="*80)
    
    def create_cost_spike_alert(self, cost_threshold: float = 0.05):
        """Create a manual cost spike alert for testing"""
        print(f"\nCreating cost spike test alert (threshold: ${cost_threshold})...")
        
        # Simulate a cost spike scenario
        high_cost_prompt = "Generate a comprehensive analysis of " + "artificial intelligence " * 1000
        
        try:
            response = self._send_request(high_cost_prompt, max_tokens=2000)
            
            if response.get("status_code") == 200:
                response_data = response.get("response_data", {})
                cost = response_data.get("cost_estimate", 0)
                
                if cost > cost_threshold:
                    print(f"✅ Cost spike detected! ${cost:.6f} exceeds threshold ${cost_threshold}")
                    return {
                        "alert_triggered": True,
                        "cost": cost,
                        "threshold": cost_threshold
                    }
                else:
                    print(f"ℹ️  Cost ${cost:.6f} below threshold ${cost_threshold}")
                    return {
                        "alert_triggered": False,
                        "cost": cost,
                        "threshold": cost_threshold
                    }
            else:
                print(f"❌ Request failed: {response.get('error', 'Unknown error')}")
                return {"alert_triggered": False, "error": response.get("error")}
                
        except Exception as e:
            print(f"❌ Error creating cost spike: {e}")
            return {"alert_triggered": False, "error": str(e)}


def main():
    """Main simulation function"""
    simulator = CostSpikeSimulator()
    
    print("SentinelLLM Cost Monitoring Testing - Cost Spike Simulation")
    print("This will test cost monitoring and alerting capabilities.")
    print("Make sure the gateway is running on http://localhost:8080")
    print("\nPress Enter to continue...")
    input()
    
    # Run the simulation
    results = simulator.run_simulation(delay=0.5)
    
    # Print summary
    simulator.print_summary(results)
    
    # Create a cost spike alert
    simulator.create_cost_spike_alert(cost_threshold=0.01)
    
    # Save results to file
    with open("cost_spike_simulation_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: cost_spike_simulation_results.json")


if __name__ == "__main__":
    main()

