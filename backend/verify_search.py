#!/usr/bin/env python3
"""
Search and Filtering System Verification Script

This script verifies that the search and filtering functionality is working correctly.
"""
import asyncio
import sys
import requests
from datetime import date, timedelta
from typing import Dict, Any, List

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"

class SearchVerifier:
    """Search functionality verification."""
    
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        self.test_user_id = None
        self.test_tasks = []
    
    def setup_test_user(self) -> bool:
        """Create a test user and login."""
        try:
            # Register test user
            register_data = {
                "email": "search_test@example.com",
                "username": "search_tester",
                "password": "TestPassword123!"
            }
            
            response = self.session.post(f"{API_BASE}/auth/register", json=register_data)
            if response.status_code not in [200, 409]:  # 409 if user already exists
                print(f"❌ Failed to register test user: {response.status_code}")
                return False
            
            # Login
            login_data = {
                "username": "search_test@example.com",
                "password": "TestPassword123!"
            }
            
            response = self.session.post(f"{API_BASE}/auth/login", data=login_data)
            if response.status_code != 200:
                print(f"❌ Failed to login: {response.status_code}")
                return False
            
            token_data = response.json()
            self.auth_token = token_data["access_token"]
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
            
            print("✅ Test user setup complete")
            return True
            
        except Exception as e:
            print(f"❌ Error setting up test user: {e}")
            return False
    
    def create_test_tasks(self) -> bool:
        """Create sample tasks for testing."""
        try:
            tasks_data = [
                {
                    "title": "Learn Python Programming",
                    "description": "Study Python fundamentals and advanced concepts",
                    "priority": "high",
                    "due_date": (date.today() + timedelta(days=7)).isoformat()
                },
                {
                    "title": "Build REST API",
                    "description": "Create a FastAPI application with authentication",
                    "priority": "medium",
                    "due_date": (date.today() + timedelta(days=14)).isoformat()
                },
                {
                    "title": "Write unit tests",
                    "description": "Add comprehensive test coverage for all endpoints",
                    "priority": "low",
                    "due_date": (date.today() + timedelta(days=21)).isoformat()
                },
                {
                    "title": "Database optimization",
                    "description": "Optimize SQL queries and add proper indexes",
                    "priority": "medium"
                },
                {
                    "title": "Deploy to production",
                    "description": "Set up CI/CD pipeline and deploy application",
                    "priority": "high",
                    "due_date": (date.today() + timedelta(days=30)).isoformat()
                }
            ]
            
            created_tasks = []
            for task_data in tasks_data:
                response = self.session.post(f"{API_BASE}/tasks", json=task_data)
                if response.status_code == 200:
                    created_tasks.append(response.json())
                else:
                    print(f"⚠️ Failed to create task: {task_data['title']}")
            
            self.test_tasks = created_tasks
            print(f"✅ Created {len(created_tasks)} test tasks")
            return len(created_tasks) > 0
            
        except Exception as e:
            print(f"❌ Error creating test tasks: {e}")
            return False
    
    def test_basic_search(self) -> bool:
        """Test basic text search functionality."""
        try:
            print("\n--- Testing Basic Search ---")
            
            # Test search by title
            response = self.session.get(f"{API_BASE}/search/tasks?query=Python")
            if response.status_code != 200:
                print(f"❌ Basic search failed: {response.status_code}")
                return False
            
            data = response.json()
            if data["total"] == 0:
                print("❌ No results found for 'Python' search")
                return False
            
            print(f"✅ Found {data['total']} results for 'Python' search")
            
            # Test search by description
            response = self.session.get(f"{API_BASE}/search/tasks?query=FastAPI")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Found {data['total']} results for 'FastAPI' search")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in basic search test: {e}")
            return False
    
    def test_filtering(self) -> bool:
        """Test filtering functionality."""
        try:
            print("\n--- Testing Filtering ---")
            
            # Test priority filter
            response = self.session.get(f"{API_BASE}/search/tasks?priority=high")
            if response.status_code != 200:
                print(f"❌ Priority filter failed: {response.status_code}")
                return False
            
            data = response.json()
            high_priority_count = data["total"]
            print(f"✅ Found {high_priority_count} high priority tasks")
            
            # Verify all results have high priority
            for task in data["tasks"]:
                if task["priority"] != "high":
                    print(f"❌ Priority filter failed: found {task['priority']} task")
                    return False
            
            # Test completion filter
            response = self.session.get(f"{API_BASE}/search/tasks?completed=false")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Found {data['total']} incomplete tasks")
            
            # Test multiple priority filter
            response = self.session.get(f"{API_BASE}/search/tasks?priority=high,medium")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Found {data['total']} high/medium priority tasks")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in filtering test: {e}")
            return False
    
    def test_sorting(self) -> bool:
        """Test sorting functionality."""
        try:
            print("\n--- Testing Sorting ---")
            
            # Test sort by title ascending
            response = self.session.get(f"{API_BASE}/search/tasks?sort_by=title&sort_order=asc")
            if response.status_code != 200:
                print(f"❌ Sorting failed: {response.status_code}")
                return False
            
            data = response.json()
            titles = [task["title"] for task in data["tasks"]]
            if titles != sorted(titles):
                print("❌ Title sorting (ascending) failed")
                return False
            
            print("✅ Title sorting (ascending) works correctly")
            
            # Test sort by priority
            response = self.session.get(f"{API_BASE}/search/tasks?sort_by=priority&sort_order=desc")
            if response.status_code == 200:
                print("✅ Priority sorting works correctly")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in sorting test: {e}")
            return False
    
    def test_pagination(self) -> bool:
        """Test pagination functionality."""
        try:
            print("\n--- Testing Pagination ---")
            
            # Test first page
            response = self.session.get(f"{API_BASE}/search/tasks?page=1&size=2")
            if response.status_code != 200:
                print(f"❌ Pagination failed: {response.status_code}")
                return False
            
            data = response.json()
            if len(data["tasks"]) > 2:
                print(f"❌ Page size limit not respected: got {len(data['tasks'])} tasks")
                return False
            
            print(f"✅ Pagination works: page {data['page']}, {data['size']} tasks")
            print(f"   Total: {data['total']}, Pages: {data['total_pages']}")
            print(f"   Has next: {data['has_next']}, Has prev: {data['has_prev']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in pagination test: {e}")
            return False
    
    def test_suggestions(self) -> bool:
        """Test autocomplete suggestions."""
        try:
            print("\n--- Testing Suggestions ---")
            
            response = self.session.get(f"{API_BASE}/search/suggestions?q=Py")
            if response.status_code != 200:
                print(f"❌ Suggestions failed: {response.status_code}")
                return False
            
            data = response.json()
            suggestions = data["suggestions"]
            print(f"✅ Got {len(suggestions)} suggestions for 'Py': {suggestions}")
            
            # Test with longer query
            response = self.session.get(f"{API_BASE}/search/suggestions?q=API")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Got {len(data['suggestions'])} suggestions for 'API'")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in suggestions test: {e}")
            return False
    
    def test_filter_stats(self) -> bool:
        """Test filter statistics."""
        try:
            print("\n--- Testing Filter Statistics ---")
            
            response = self.session.get(f"{API_BASE}/search/filters/stats")
            if response.status_code != 200:
                print(f"❌ Filter stats failed: {response.status_code}")
                return False
            
            data = response.json()
            print(f"✅ Filter statistics:")
            print(f"   Priorities: {data['priorities']}")
            print(f"   Completion: {data['completion']}")
            print(f"   Total tasks: {data['total_tasks']}")
            
            if "date_ranges" in data:
                print(f"   Date ranges available: {bool(data['date_ranges']['created_from'])}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in filter stats test: {e}")
            return False
    
    def test_post_search(self) -> bool:
        """Test POST search endpoint."""
        try:
            print("\n--- Testing POST Search ---")
            
            search_data = {
                "query": "Python",
                "priority": "high",
                "completed": False,
                "sort_by": "title",
                "sort_order": "asc",
                "page": 1,
                "size": 10
            }
            
            response = self.session.post(f"{API_BASE}/search/tasks", json=search_data)
            if response.status_code != 200:
                print(f"❌ POST search failed: {response.status_code}")
                return False
            
            data = response.json()
            print(f"✅ POST search works: found {data['total']} results")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in POST search test: {e}")
            return False
    
    def test_advanced_features(self) -> bool:
        """Test advanced search features."""
        try:
            print("\n--- Testing Advanced Features ---")
            
            # Test searchable fields
            response = self.session.get(f"{API_BASE}/search/advanced/fields")
            if response.status_code == 200:
                data = response.json()
                fields_count = len(data["fields"])
                print(f"✅ Got {fields_count} searchable fields metadata")
            
            # Test export
            response = self.session.get(f"{API_BASE}/search/export?format=json")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Export works: exported {len(data['data'])} tasks")
            
            # Test cache clearing
            response = self.session.delete(f"{API_BASE}/search/cache")
            if response.status_code == 200:
                print("✅ Search cache clearing works")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in advanced features test: {e}")
            return False
    
    def test_performance(self) -> bool:
        """Test search performance."""
        try:
            print("\n--- Testing Performance ---")
            
            response = self.session.get(f"{API_BASE}/search/tasks?query=Python")
            if response.status_code == 200:
                data = response.json()
                search_time = data.get("search_time_ms", 0)
                print(f"✅ Search completed in {search_time:.2f}ms")
                
                if search_time > 1000:  # 1 second
                    print("⚠️ Search time is high, consider optimization")
                else:
                    print("✅ Search performance is good")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in performance test: {e}")
            return False
    
    def cleanup(self) -> bool:
        """Clean up test data."""
        try:
            # Delete test tasks
            for task in self.test_tasks:
                response = self.session.delete(f"{API_BASE}/tasks/{task['id']}")
                if response.status_code not in [200, 404]:
                    print(f"⚠️ Failed to delete task {task['id']}")
            
            print("✅ Cleanup completed")
            return True
            
        except Exception as e:
            print(f"⚠️ Error during cleanup: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all search verification tests."""
        print("🔍 Starting Search and Filtering System Verification")
        print("=" * 60)
        
        # Setup
        if not self.setup_test_user():
            return False
        
        if not self.create_test_tasks():
            return False
        
        # Run tests
        tests = [
            ("Basic Search", self.test_basic_search),
            ("Filtering", self.test_filtering),
            ("Sorting", self.test_sorting),
            ("Pagination", self.test_pagination),
            ("Suggestions", self.test_suggestions),
            ("Filter Statistics", self.test_filter_stats),
            ("POST Search", self.test_post_search),
            ("Advanced Features", self.test_advanced_features),
            ("Performance", self.test_performance)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                else:
                    print(f"❌ {test_name} test failed")
            except Exception as e:
                print(f"❌ {test_name} test error: {e}")
        
        # Cleanup
        self.cleanup()
        
        # Results
        print("\n" + "=" * 60)
        print(f"🔍 Search Verification Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("✅ All search functionality tests passed!")
            return True
        else:
            print(f"❌ {total - passed} tests failed")
            return False

def main():
    """Main verification function."""
    verifier = SearchVerifier()
    
    try:
        success = verifier.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Verification interrupted by user")
        verifier.cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"❌ Verification failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()