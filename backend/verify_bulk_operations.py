#!/usr/bin/env python3
"""
Bulk Operations and Task Management Verification Script

This script verifies that bulk operations functionality is working correctly.
"""
import sys
import time
import requests
from typing import Dict, Any, List

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"

class BulkOperationsVerifier:
    """Bulk operations functionality verification."""
    
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        self.test_tasks = []
        self.created_task_ids = []
    
    def setup_test_user(self) -> bool:
        """Create a test user and login."""
        try:
            # Register test user
            register_data = {
                "email": "bulk_test@example.com",
                "username": "bulk_tester",
                "password": "TestPassword123!"
            }
            
            response = self.session.post(f"{API_BASE}/auth/register", json=register_data)
            if response.status_code not in [200, 409]:
                print(f"❌ Failed to register test user: {response.status_code}")
                return False
            
            # Login
            login_data = {
                "username": "bulk_test@example.com",
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
    
    def test_bulk_create(self) -> bool:
        """Test bulk task creation."""
        try:
            print("\n--- Testing Bulk Task Creation ---")
            
            tasks_data = [
                {
                    "title": "Bulk Task 1",
                    "description": "First bulk created task",
                    "priority": "high"
                },
                {
                    "title": "Bulk Task 2",
                    "description": "Second bulk created task",
                    "priority": "medium"
                },
                {
                    "title": "Bulk Task 3",
                    "description": "Third bulk created task",
                    "priority": "low"
                },
                {
                    "title": "Bulk Task 4",
                    "description": "Fourth bulk created task",
                    "priority": "medium"
                },
                {
                    "title": "Bulk Task 5",
                    "description": "Fifth bulk created task",
                    "priority": "high"
                }
            ]
            
            response = self.session.post(
                f"{API_BASE}/bulk/create",
                json={"tasks": tasks_data}
            )
            
            if response.status_code != 200:
                print(f"❌ Bulk create failed: {response.status_code}")
                return False
            
            data = response.json()
            created_tasks = data["created_tasks"]
            self.created_task_ids = [task["id"] for task in created_tasks]
            
            print(f"✅ Created {len(created_tasks)} tasks in bulk")
            print(f"   Operation ID: {data['operation_id']}")
            print(f"   Status: {data['status']}")
            print(f"   Progress: {data['progress_percentage']:.1f}%")
            
            # Verify all tasks were created
            if len(created_tasks) != len(tasks_data):
                print(f"❌ Expected {len(tasks_data)} tasks, got {len(created_tasks)}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error in bulk create test: {e}")
            return False
    
    def test_bulk_update(self) -> bool:
        """Test bulk task updates."""
        try:
            print("\n--- Testing Bulk Task Updates ---")
            
            if not self.created_task_ids:
                print("❌ No tasks available for update test")
                return False
            
            # Test bulk status change
            task_ids = self.created_task_ids[:3]  # First 3 tasks
            response = self.session.put(
                f"{API_BASE}/bulk/status",
                json={
                    "task_ids": task_ids,
                    "completed": True
                }
            )
            
            if response.status_code != 200:
                print(f"❌ Bulk status change failed: {response.status_code}")
                return False
            
            data = response.json()
            print(f"✅ Bulk status change completed")
            print(f"   Marked {data['processed_items']} tasks as completed")
            
            # Test bulk priority change
            response = self.session.put(
                f"{API_BASE}/bulk/priority",
                json={
                    "task_ids": self.created_task_ids,
                    "priority": "high"
                }
            )
            
            if response.status_code != 200:
                print(f"❌ Bulk priority change failed: {response.status_code}")
                return False
            
            data = response.json()
            print(f"✅ Bulk priority change completed")
            print(f"   Changed {data['processed_items']} tasks to high priority")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in bulk update test: {e}")
            return False
    
    def test_bulk_duplicate(self) -> bool:
        """Test bulk task duplication."""
        try:
            print("\n--- Testing Bulk Task Duplication ---")
            
            if len(self.created_task_ids) < 2:
                print("❌ Not enough tasks for duplication test")
                return False
            
            task_ids = self.created_task_ids[:2]  # Duplicate first 2 tasks
            response = self.session.post(
                f"{API_BASE}/bulk/duplicate",
                json={
                    "task_ids": task_ids,
                    "suffix": " (Copy)"
                }
            )
            
            if response.status_code != 200:
                print(f"❌ Bulk duplicate failed: {response.status_code}")
                return False
            
            data = response.json()
            duplicated_tasks = data["duplicated_tasks"]
            
            print(f"✅ Duplicated {len(duplicated_tasks)} tasks")
            print(f"   Operation ID: {data['operation_id']}")
            
            # Verify duplicated tasks have the suffix
            for task in duplicated_tasks:
                if "(Copy)" not in task["title"]:
                    print(f"❌ Duplicated task missing suffix: {task['title']}")
                    return False
                
                # Store for cleanup
                self.created_task_ids.append(task["id"])
            
            print("✅ All duplicated tasks have correct suffix")
            return True
            
        except Exception as e:
            print(f"❌ Error in bulk duplicate test: {e}")
            return False
    
    def test_reorder_tasks(self) -> bool:
        """Test task reordering."""
        try:
            print("\n--- Testing Task Reordering ---")
            
            if len(self.created_task_ids) < 3:
                print("❌ Not enough tasks for reordering test")
                return False
            
            # Create reorder positions
            task_positions = [
                {"id": self.created_task_ids[0], "position": 2},
                {"id": self.created_task_ids[1], "position": 0},
                {"id": self.created_task_ids[2], "position": 1}
            ]
            
            response = self.session.put(
                f"{API_BASE}/bulk/reorder",
                json={"task_positions": task_positions}
            )
            
            if response.status_code != 200:
                print(f"❌ Task reorder failed: {response.status_code}")
                return False
            
            data = response.json()
            print(f"✅ Reordered {data['processed_items']} tasks")
            print(f"   Operation ID: {data['operation_id']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in task reorder test: {e}")
            return False
    
    def test_operation_status(self) -> bool:
        """Test operation status tracking."""
        try:
            print("\n--- Testing Operation Status Tracking ---")
            
            # Create an operation to track
            response = self.session.put(
                f"{API_BASE}/bulk/status",
                json={
                    "task_ids": self.created_task_ids[:2],
                    "completed": False
                }
            )
            
            if response.status_code != 200:
                print(f"❌ Failed to create operation for status test")
                return False
            
            operation_id = response.json()["operation_id"]
            
            # Check operation status
            response = self.session.get(
                f"{API_BASE}/bulk/status/{operation_id}"
            )
            
            if response.status_code != 200:
                print(f"❌ Failed to get operation status: {response.status_code}")
                return False
            
            data = response.json()
            print(f"✅ Operation status retrieved")
            print(f"   Operation ID: {data['operation_id']}")
            print(f"   Status: {data['status']}")
            print(f"   Progress: {data['progress_percentage']:.1f}%")
            print(f"   Processed: {data['processed_items']}/{data['total_items']}")
            print(f"   Is Completed: {data['is_completed']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in operation status test: {e}")
            return False
    
    def test_task_templates(self) -> bool:
        """Test task templates functionality."""
        try:
            print("\n--- Testing Task Templates ---")
            
            # Create a template
            template_data = {
                "name": "Project Setup Template",
                "description": "Standard project setup tasks",
                "category": "development",
                "tasks": [
                    {
                        "title": "Initialize Git Repository",
                        "description": "Set up version control",
                        "priority": "high"
                    },
                    {
                        "title": "Setup Development Environment",
                        "description": "Configure development tools",
                        "priority": "medium"
                    },
                    {
                        "title": "Create Documentation",
                        "description": "Write project documentation",
                        "priority": "low"
                    }
                ]
            }
            
            response = self.session.post(
                f"{API_BASE}/bulk/templates",
                json=template_data
            )
            
            if response.status_code != 200:
                print(f"❌ Template creation failed: {response.status_code}")
                return False
            
            template_id = response.json()["template_id"]
            print(f"✅ Template created: {template_id}")
            
            # Get templates
            response = self.session.get(f"{API_BASE}/bulk/templates")
            
            if response.status_code != 200:
                print(f"❌ Failed to get templates: {response.status_code}")
                return False
            
            templates = response.json()["templates"]
            print(f"✅ Retrieved {len(templates)} templates")
            
            # Apply template
            response = self.session.post(
                f"{API_BASE}/bulk/templates/apply",
                json={
                    "template_id": template_id,
                    "customizations": {"priority": "medium"}
                }
            )
            
            if response.status_code != 200:
                print(f"❌ Template application failed: {response.status_code}")
                return False
            
            data = response.json()
            created_tasks = data["created_tasks"]
            
            # Store for cleanup
            self.created_task_ids.extend([task["id"] for task in created_tasks])
            
            print(f"✅ Template applied: created {len(created_tasks)} tasks")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in template test: {e}")
            return False
    
    def test_undo_functionality(self) -> bool:
        """Test undo functionality."""
        try:
            print("\n--- Testing Undo Functionality ---")
            
            # Get undo history
            response = self.session.get(f"{API_BASE}/bulk/undo/history")
            
            if response.status_code != 200:
                print(f"❌ Failed to get undo history: {response.status_code}")
                return False
            
            history = response.json()["undo_history"]
            print(f"✅ Retrieved undo history: {len(history)} operations")
            
            if history:
                print("   Recent operations:")
                for i, op in enumerate(history[:3]):  # Show first 3
                    print(f"     {i+1}. {op['operation_type']} - {op['total_items']} items")
            
            # Try to undo the most recent operation
            response = self.session.post(f"{API_BASE}/bulk/undo")
            
            if response.status_code == 200:
                print("✅ Undo operation successful")
            elif response.status_code == 400:
                print("⚠️ No operation to undo (expected if no undoable operations)")
            else:
                print(f"❌ Undo failed: {response.status_code}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error in undo test: {e}")
            return False
    
    def test_keyboard_shortcuts(self) -> bool:
        """Test keyboard shortcuts information."""
        try:
            print("\n--- Testing Keyboard Shortcuts Support ---")
            
            response = self.session.get(f"{API_BASE}/bulk/shortcuts")
            
            if response.status_code != 200:
                print(f"❌ Failed to get shortcuts: {response.status_code}")
                return False
            
            data = response.json()
            shortcuts = data["shortcuts"]
            bulk_ops = data["bulk_operations"]
            
            print(f"✅ Retrieved {len(shortcuts)} keyboard shortcuts")
            print("   Available shortcuts:")
            for shortcut, description in list(shortcuts.items())[:5]:  # Show first 5
                print(f"     {shortcut}: {description}")
            
            print(f"✅ Retrieved {len(bulk_ops)} bulk operation endpoints")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in shortcuts test: {e}")
            return False
    
    def test_bulk_delete(self) -> bool:
        """Test bulk task deletion."""
        try:
            print("\n--- Testing Bulk Task Deletion ---")
            
            if len(self.created_task_ids) < 2:
                print("❌ Not enough tasks for deletion test")
                return False
            
            # Delete half of the tasks
            delete_count = len(self.created_task_ids) // 2
            tasks_to_delete = self.created_task_ids[:delete_count]
            
            response = self.session.delete(
                f"{API_BASE}/bulk/delete",
                json={"task_ids": tasks_to_delete}
            )
            
            if response.status_code != 200:
                print(f"❌ Bulk delete failed: {response.status_code}")
                return False
            
            data = response.json()
            print(f"✅ Bulk delete completed")
            print(f"   Deleted {data['processed_items']} tasks")
            print(f"   Operation ID: {data['operation_id']}")
            
            # Remove deleted tasks from our list
            self.created_task_ids = self.created_task_ids[delete_count:]
            
            return True
            
        except Exception as e:
            print(f"❌ Error in bulk delete test: {e}")
            return False
    
    def test_validation(self) -> bool:
        """Test input validation."""
        try:
            print("\n--- Testing Input Validation ---")
            
            # Test empty task list
            response = self.session.post(
                f"{API_BASE}/bulk/create",
                json={"tasks": []}
            )
            
            if response.status_code == 422:
                print("✅ Empty task list validation works")
            else:
                print("❌ Empty task list validation failed")
                return False
            
            # Test invalid priority
            response = self.session.put(
                f"{API_BASE}/bulk/priority",
                json={
                    "task_ids": [999],  # Non-existent task
                    "priority": "invalid"
                }
            )
            
            if response.status_code == 422:
                print("✅ Invalid priority validation works")
            else:
                print("❌ Invalid priority validation failed")
                return False
            
            # Test task limit (try to create too many)
            large_task_list = [{"title": f"Task {i}"} for i in range(101)]
            response = self.session.post(
                f"{API_BASE}/bulk/create",
                json={"tasks": large_task_list}
            )
            
            if response.status_code == 422:
                print("✅ Task limit validation works")
            else:
                print("❌ Task limit validation failed")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error in validation test: {e}")
            return False
    
    def cleanup(self) -> bool:
        """Clean up test data."""
        try:
            if self.created_task_ids:
                print(f"\n--- Cleaning up {len(self.created_task_ids)} test tasks ---")
                
                # Delete remaining tasks
                response = self.session.delete(
                    f"{API_BASE}/bulk/delete",
                    json={"task_ids": self.created_task_ids}
                )
                
                if response.status_code == 200:
                    print("✅ Cleanup completed successfully")
                else:
                    print(f"⚠️ Cleanup partially failed: {response.status_code}")
            
            return True
            
        except Exception as e:
            print(f"⚠️ Error during cleanup: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all bulk operations verification tests."""
        print("⚙️ Starting Bulk Operations and Task Management Verification")
        print("=" * 70)
        
        # Setup
        if not self.setup_test_user():
            return False
        
        # Run tests
        tests = [
            ("Bulk Task Creation", self.test_bulk_create),
            ("Bulk Task Updates", self.test_bulk_update), 
            ("Bulk Task Duplication", self.test_bulk_duplicate),
            ("Task Reordering", self.test_reorder_tasks),
            ("Operation Status Tracking", self.test_operation_status),
            ("Task Templates", self.test_task_templates),
            ("Undo Functionality", self.test_undo_functionality),
            ("Keyboard Shortcuts", self.test_keyboard_shortcuts),
            ("Bulk Task Deletion", self.test_bulk_delete),
            ("Input Validation", self.test_validation)
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
        print("\n" + "=" * 70)
        print(f"⚙️ Bulk Operations Verification Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("✅ All bulk operations functionality tests passed!")
            return True
        else:
            print(f"❌ {total - passed} tests failed")
            return False

def main():
    """Main verification function."""
    verifier = BulkOperationsVerifier()
    
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