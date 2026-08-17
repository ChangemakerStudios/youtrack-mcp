"""
YouTrack Projects API client.
"""

from typing import Any, Dict, List, Optional
import json

from pydantic import BaseModel, Field

from youtrack_mcp.api.client import YouTrackClient
import logging

logger = logging.getLogger(__name__)


class Project(BaseModel):
    """Model for a YouTrack project."""

    id: str
    name: str
    shortName: str
    description: Optional[str] = None
    archived: bool = False
    created: Optional[int] = None
    updated: Optional[int] = None
    lead: Optional[Dict[str, Any]] = None
    custom_fields: List[Dict[str, Any]] = Field(default_factory=list)


class ProjectsClient:
    """Client for interacting with YouTrack Projects API."""

    def __init__(self, client: YouTrackClient):
        """
        Initialize the Projects API client.

        Args:
            client: The YouTrack API client
        """
        self.client = client

    def get_projects(
        self, include_archived: bool = False, page_size: int = 100
    ) -> List[Project]:
        """
        Get all projects with pagination support.

        This method fetches all projects by iterating through pages of results.
        YouTrack API limits results per request, so pagination is required
        for instances with many projects (>50).

        Args:
            include_archived: Whether to include archived projects
            page_size: Number of projects to fetch per page (default: 100)

        Returns:
            List of all projects
        """
        all_projects: List[Project] = []
        skip = 0
        fields = "id,name,shortName,description,archived,created,updated,lead(id,name,login)"

        while True:
            params = {
                "fields": fields,
                "$top": page_size,
                "$skip": skip,
            }
            if not include_archived:
                params["$filter"] = "archived eq false"

            logger.debug(f"Fetching projects page: skip={skip}, top={page_size}")
            response = self.client.get("admin/projects", params=params)

            if not response:
                # No more projects
                break

            projects = [Project.model_validate(project) for project in response]
            all_projects.extend(projects)

            logger.debug(f"Fetched {len(projects)} projects (total: {len(all_projects)})")

            if len(projects) < page_size:
                # Last page - fewer results than requested
                break

            skip += page_size

        logger.info(f"Retrieved {len(all_projects)} total projects")
        return all_projects

    def get_project(self, project_id: str) -> Project:
        """
        Get a project by ID.

        Args:
            project_id: The project ID

        Returns:
            The project data
        """
        response = self.client.get(
            f"admin/projects/{project_id}",
            params={
                "fields": "id,name,shortName,description,archived,created,updated,lead(id,name,login)"
            },
        )
        return Project.model_validate(response)

    def get_project_by_name(self, project_name: str) -> Optional[Project]:
        """
        Get a project by its name or short name.

        This method uses an efficient lookup strategy:
        1. First, try direct API lookup by shortName (most efficient)
        2. If that fails, fetch all projects with pagination and match client-side

        Args:
            project_name: The project name or short name

        Returns:
            The project data or None if not found
        """
        # Strategy 1: Try direct API lookup by shortName (most efficient)
        # YouTrack allows fetching a project directly by its shortName
        try:
            logger.debug(f"Attempting direct project lookup: {project_name}")
            response = self.client.get(
                f"admin/projects/{project_name}",
                params={
                    "fields": "id,name,shortName,description,archived,created,updated,lead(id,name,login)"
                },
            )
            if response:
                project = Project.model_validate(response)
                logger.info(f"Found project by direct lookup: {project.name} ({project.shortName})")
                return project
        except Exception as e:
            # Direct lookup failed, this is expected for full names
            logger.debug(f"Direct project lookup failed for '{project_name}': {e}")

        # Strategy 2: Fetch all projects with pagination and match client-side
        logger.debug(f"Falling back to full project search for: {project_name}")
        projects = self.get_projects(include_archived=True)

        # First try to match by short name (exact match, case-insensitive)
        for project in projects:
            if project.shortName.lower() == project_name.lower():
                logger.info(f"Found project by shortName match: {project.name}")
                return project

        # Then try to match by full name (case-insensitive)
        for project in projects:
            if project.name.lower() == project_name.lower():
                logger.info(f"Found project by name match: {project.name}")
                return project

        # Finally try to match if project_name is contained in the name
        for project in projects:
            if project_name.lower() in project.name.lower():
                logger.info(f"Found project by partial name match: {project.name}")
                return project

        logger.warning(f"Project not found: {project_name}")
        return None

    def get_project_issues(
        self, project_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get issues for a specific project.

        Args:
            project_id: The project ID
            limit: Maximum number of issues to return

        Returns:
            List of issues in the project
        """
        logger.info(f"Getting issues for project {project_id}, limit {limit}")

        # Request more fields to get complete issue information
        fields = "id,summary,description,created,updated,reporter(id,login,name),assignee(id,login,name),project(id,name,shortName),customFields(id,name,value($type,name,text,id),projectCustomField(field(name)))"

        params = {
            "$filter": f"project/id eq {project_id}",
            "$top": limit,
            "fields": fields,
        }

        try:
            issues = self.client.get("issues", params=params)
            logger.info(
                f"Retrieved {len(issues) if isinstance(issues, list) else 0} issues"
            )
            return issues
        except Exception as e:
            logger.error(
                f"Error getting issues for project {project_id}: {str(e)}"
            )
            # Return empty list on error
            return []

    def create_project(
        self,
        name: str,
        short_name: str,
        description: Optional[str] = None,
        lead_id: Optional[str] = None,
    ) -> Project:
        """
        Create a new project.

        Args:
            name: The project name
            short_name: The project short name (used in issue IDs)
            description: Optional project description
            lead_id: Optional project lead user ID

        Returns:
            The created project data
        """
        if not name:
            raise ValueError("Project name is required")
        if not short_name:
            raise ValueError("Project short name is required")

        data = {"name": name, "shortName": short_name}

        if description:
            data["description"] = description

        if lead_id:
            # The YouTrack API expects "leader", not "lead_id"
            data["leader"] = {"id": lead_id}

        # Debug logging
        logger.info(f"Creating project with data: {json.dumps(data)}")
        logger.info(
            f"Base URL: {self.client.base_url}, API endpoint: admin/projects"
        )

        try:
            response = self.client.post("admin/projects", data=data)
            logger.info(f"Create project response: {json.dumps(response)}")

            # The response might not include all required fields,
            # Try to get the complete project now
            if isinstance(response, dict) and "id" in response:
                try:
                    # Get the full project details
                    created_project = self.get_project(response["id"])
                    logger.info(
                        f"Successfully retrieved full project details: {created_project.name}"
                    )
                    return created_project
                except Exception as e:
                    logger.warning(
                        f"Could not retrieve full project details: {str(e)}"
                    )
                    # Fall back to creating a model with the available data
                    # We need to ensure shortName is present
                    if "shortName" not in response and short_name:
                        response["shortName"] = short_name
                    if "name" not in response and name:
                        response["name"] = name

            # Try to validate the model, which might fail if fields are missing
            try:
                return Project.model_validate(response)
            except Exception as e:
                logger.warning(f"Could not validate project model: {str(e)}")
                # As a last resort, create a minimal valid project
                minimal_project = {
                    "id": response.get("id", "unknown"),
                    "name": name,
                    "shortName": short_name,
                    "description": description,
                }
                return Project.model_validate(minimal_project)
        except Exception as e:
            logger.error(f"Error creating project: {str(e)}")
            raise

    def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        lead_id: Optional[str] = None,
        archived: Optional[bool] = None,
    ) -> Project:
        """
        Update an existing project.

        Args:
            project_id: The project ID
            name: The new project name
            description: The new project description
            lead_id: The new project lead user ID
            archived: Whether the project should be archived

        Returns:
            The updated project data
        """
        # First get the existing project data
        logger.info(f"Getting existing project data for {project_id}")

        try:
            # Prepare data for update API call
            data = {}

            # Include any provided parameters
            if name is not None:
                data["name"] = name
            if description is not None:
                data["description"] = description
            if lead_id is not None:
                data["leader"] = {"id": lead_id}
            if archived is not None:
                data["archived"] = archived

            # Make sure we have at least one parameter to update
            if not data:
                logger.info(
                    "No parameters to update, returning current project data"
                )
                return self.get_project(project_id)

            logger.info(f"Updating project with data: {data}")
            response = self.client.post(
                f"admin/projects/{project_id}", data=data
            )
            logger.info(f"Update project response: {response}")

            # The API response might not contain all required fields,
            # so we need to get the full project data after the update
            try:
                # Get the updated project data
                updated_project = self.get_project(project_id)
                logger.info(
                    f"Successfully retrieved updated project: {updated_project.name}"
                )
                return updated_project
            except Exception as e:
                logger.error(f"Error getting updated project: {str(e)}")
                # If we can't get the updated project, create a partial project with the data we have
                if isinstance(response, dict) and "id" in response:
                    logger.info(
                        f"Creating partial project from response: {response}"
                    )
                    # Try to get the original project to fill in missing fields
                    try:
                        original_project = self.get_project(project_id)
                        # Update with new values
                        for key, value in data.items():
                            if key == "leader":
                                setattr(original_project, "lead", value)
                            else:
                                setattr(original_project, key, value)
                        return original_project
                    except Exception:
                        # If we can't get the original project either, just return the response
                        logger.warning(
                            f"Unable to get original project, returning response: {response}"
                        )
                        return response
                else:
                    # If the response doesn't have an ID, just return it
                    return response
        except Exception as e:
            logger.error(f"Error updating project {project_id}: {str(e)}")
            raise

    def delete_project(self, project_id: str) -> None:
        """
        Delete a project.

        Args:
            project_id: The project ID
        """
        self.client.delete(f"admin/projects/{project_id}")

    def get_custom_fields(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Get custom fields for a project.

        Args:
            project_id: The project ID

        Returns:
            List of custom fields
        """
        return self.client.get(f"admin/projects/{project_id}/customFields")

    def add_custom_field(
        self,
        project_id: str,
        field_id: str,
        empty_field_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a custom field to a project.

        Args:
            project_id: The project ID
            field_id: The custom field ID
            empty_field_text: Optional text to show for empty fields

        Returns:
            The added custom field
        """
        data = {"field": {"id": field_id}}

        if empty_field_text:
            data["emptyFieldText"] = empty_field_text

        return self.client.post(
            f"admin/projects/{project_id}/customFields", data=data
        )

    def get_custom_field_schema(
        self, project_id: str, field_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed schema for a specific custom field.

        Args:
            project_id: The project ID
            field_name: The custom field name

        Returns:
            Custom field schema with type information and constraints
        """
        try:
            # Use detailed fields query to get complete information
            fields_query = "field(id,name,fieldType($type,valueType,id)),canBeEmpty,autoAttached"
            fields = self.client.get(f"admin/projects/{project_id}/customFields?fields={fields_query}")
            
            for field in fields:
                if field.get("field", {}).get("name") == field_name:
                    field_schema = field.get("field", {})
                    field_type = field_schema.get("fieldType", {})
                    
                    enhanced_schema = {
                        "name": field_name,
                        "type": field_type.get("valueType", "string"),
                        "bundle_type": field_type.get("$type", ""),
                        "required": field.get("canBeEmpty", True) == False,
                        "multi_value": field_schema.get("isMultiValue", False),
                        "auto_attach": field.get("autoAttached", False),
                        "field_id": field_schema.get("id"),
                        "bundle_id": field_type.get("id")
                    }
                    
                    logger.info(f"Found schema for field '{field_name}': {enhanced_schema}")
                    
                    # Add allowed values for enum/state fields
                    if field_type.get("valueType") in ["enum", "state"]:
                        try:
                            enhanced_schema["allowed_values"] = self.get_custom_field_allowed_values(project_id, field_name)
                        except Exception as e:
                            logger.warning(f"Could not get allowed values for {field_name}: {str(e)}")
                            enhanced_schema["allowed_values"] = []
                    
                    return enhanced_schema
            
            logger.warning(f"Field '{field_name}' not found in project {project_id} custom fields")
            return None
        except Exception as e:
            logger.error(f"Error getting custom field schema for '{field_name}': {str(e)}")
            return None

    _BUNDLE_KINDS = {
        "EnumProjectCustomField": "enum",
        "StateProjectCustomField": "state",
        "OwnedProjectCustomField": "ownedField",
        "VersionProjectCustomField": "version",
        "BuildProjectCustomField": "build",
        "UserProjectCustomField": "user",
    }

    def get_custom_field_allowed_values(self, project_id: str, field_name: str) -> List[Dict[str, Any]]:
        """
        Get allowed values for a custom field in a specific project.

        The bundle id must come from the project field itself (bundle(id));
        fieldType ids like "enum[1]" describe single/multi arity, not which
        bundle the field uses.

        Args:
            project_id: The project identifier
            field_name: The custom field name

        Returns:
            List of allowed values with id, name, and other properties
        """
        try:
            fields_query = "field(id,name),bundle(id,name),$type"
            fields = self.client.get(f"admin/projects/{project_id}/customFields?fields={fields_query}")

            field_info = None
            wanted = field_name.lower()
            for field in fields:
                if field.get("field", {}).get("name", "").lower() == wanted:
                    field_info = field
                    break

            if not field_info:
                logger.warning(f"Field '{field_name}' not found in project {project_id}")
                return []

            kind = self._BUNDLE_KINDS.get(field_info.get("$type"))
            bundle = field_info.get("bundle") or {}
            bundle_id = bundle.get("id")

            if not kind or not bundle_id:
                logger.info(f"Field '{field_name}' ({field_info.get('$type')}) has no value bundle")
                return []

            if kind == "user":
                data = self.client.get(
                    f"admin/customFieldSettings/bundles/user/{bundle_id}?fields=aggregatedUsers(id,login,name,email)"
                )
                return data.get("aggregatedUsers") or []

            value_fields = "id,name,description"
            if kind == "state":
                value_fields += ",isResolved"
            elif kind == "version":
                value_fields += ",released,releaseDate,archived"

            data = self.client.get(
                f"admin/customFieldSettings/bundles/{kind}/{bundle_id}?fields=values({value_fields})"
            )
            values = data.get("values") or []
            if kind == "state":
                for value in values:
                    value["resolved"] = value.get("isResolved", False)

            logger.info(f"Found {len(values)} values for field '{field_name}' from bundle '{bundle.get('name')}'")
            return values

        except Exception as e:
            logger.error(f"Error getting custom field allowed values for '{field_name}': {str(e)}")
            return []

    def get_available_custom_field_values(
        self, project_id: str, field_name: str
    ) -> List[Dict[str, Any]]:
        """
        Alias for get_custom_field_allowed_values for backward compatibility.
        
        Args:
            project_id: The project ID
            field_name: The custom field name

        Returns:
            List of allowed values with details
        """
        return self.get_custom_field_allowed_values(project_id, field_name)

    def get_all_custom_fields_schemas(
        self, project_id: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get schemas for all custom fields in a project.

        Args:
            project_id: The project ID

        Returns:
            Dictionary mapping field names to their schemas
        """
        try:
            # Use the same detailed query that works in other methods
            fields_query = "field(id,name,fieldType($type,valueType,id)),canBeEmpty,autoAttached"
            fields = self.client.get(f"admin/projects/{project_id}/customFields?fields={fields_query}")
            schemas = {}
            
            logger.info(f"Got {len(fields)} custom fields for project {project_id}")
            
            for field in fields:
                # Extract field name from the correct structure
                field_info = field.get("field", {})
                field_name = field_info.get("name")
                
                if field_name:
                    logger.info(f"Processing field: {field_name}")
                    # Build schema directly from the field data we already have
                    field_type = field_info.get("fieldType", {})
                    
                    enhanced_schema = {
                        "name": field_name,
                        "type": field_type.get("valueType", "string"),
                        "bundle_type": field_type.get("$type", ""),
                        "required": field.get("canBeEmpty", True) == False,
                        "multi_value": field_info.get("isMultiValue", False),
                        "auto_attach": field.get("autoAttached", False),
                        "field_id": field_info.get("id"),
                        "bundle_id": field_type.get("id")
                    }
                    
                    # Add allowed values for enum/state fields
                    if field_type.get("valueType") in ["enum", "state"]:
                        try:
                            enhanced_schema["allowed_values"] = self.get_custom_field_allowed_values(project_id, field_name)
                        except Exception as e:
                            logger.warning(f"Could not get allowed values for {field_name}: {str(e)}")
                            enhanced_schema["allowed_values"] = []
                    
                    schemas[field_name] = enhanced_schema
                    logger.info(f"Added schema for field '{field_name}': {enhanced_schema}")
                else:
                    logger.warning(f"Field missing name: {field}")
            
            logger.info(f"Returning {len(schemas)} schemas for project {project_id}")
            return schemas
        except Exception as e:
            logger.error(f"Error getting all custom field schemas: {str(e)}")
            return {}

    def validate_custom_field_for_project(
        self, 
        project_id: str, 
        field_name: str, 
        field_value: Any
    ) -> Dict[str, Any]:
        """
        Validate a custom field value against project schema.

        Args:
            project_id: The project ID
            field_name: The custom field name
            field_value: The value to validate

        Returns:
            Dictionary with validation result
        """
        try:
            # Get field schema directly using the same approach as issues.py
            field_schema = self.get_custom_field_schema(project_id, field_name)
            if not field_schema:
                return {
                    "valid": False,
                    "error": f"Custom field '{field_name}' not found in project {project_id}",
                    "suggestion": "Check field name spelling and project configuration"
                }
            
            value_type = field_schema.get("type", "")  # This is the valueType from API
            bundle_type = field_schema.get("bundle_type", "")  # This is the $type
            
            # Check if field is required and value is empty
            if field_schema.get("required", False) and (field_value is None or str(field_value).strip() == ""):
                return {
                    "valid": False,
                    "error": f"Field '{field_name}' is required and cannot be empty",
                    "suggestion": "Provide a valid value for this required field"
                }
            
            # Type-specific validation using the correct valueType
            if value_type == "state":
                # State field - validate against available states
                allowed_values = self.get_custom_field_allowed_values(project_id, field_name)
                allowed_names = [v.get("name", "") for v in allowed_values if isinstance(v, dict)]
                if str(field_value) not in allowed_names:
                    return {
                        "valid": False,
                        "error": f"Invalid state value '{field_value}' for field '{field_name}'",
                        "suggestion": f"Use one of: {', '.join(allowed_names)}" if allowed_names else "Check field configuration"
                    }
            
            elif value_type == "enum":
                # Enum field - validate against enum values
                allowed_values = self.get_custom_field_allowed_values(project_id, field_name)
                allowed_names = [v.get("name", "") for v in allowed_values if isinstance(v, dict)]
                if str(field_value) not in allowed_names:
                    return {
                        "valid": False,
                        "error": f"Invalid enum value '{field_value}' for field '{field_name}'",
                        "suggestion": f"Use one of: {', '.join(allowed_names)}" if allowed_names else "Check field configuration"
                    }
            
            elif value_type == "user":
                # User field - validate against available users
                allowed_values = self.get_custom_field_allowed_values(project_id, field_name)
                allowed_logins = [v.get("login", "") for v in allowed_values if isinstance(v, dict)]
                allowed_names = [v.get("name", "") for v in allowed_values if isinstance(v, dict)]
                if str(field_value) not in allowed_logins and str(field_value) not in allowed_names:
                    return {
                        "valid": False,
                        "error": f"User '{field_value}' not found",
                        "suggestion": f"Use valid user login: {', '.join(allowed_logins[:5])}" if allowed_logins else "Check user exists"
                    }
            
            elif value_type == "ownedField":
                # Subsystem field - validate against available subsystems
                allowed_values = self.get_custom_field_allowed_values(project_id, field_name)
                allowed_names = [v.get("name", "") for v in allowed_values if isinstance(v, dict)]
                if str(field_value) not in allowed_names:
                    return {
                        "valid": False,
                        "error": f"Invalid subsystem '{field_value}' for field '{field_name}'",
                        "suggestion": f"Use one of: {', '.join(allowed_names)}" if allowed_names else "Create subsystem first"
                    }
            
            elif value_type == "version":
                # Version field - validate against available versions
                allowed_values = self.get_custom_field_allowed_values(project_id, field_name)
                allowed_names = [v.get("name", "") for v in allowed_values if isinstance(v, dict)]
                if str(field_value) not in allowed_names:
                    return {
                        "valid": False,
                        "error": f"Invalid version '{field_value}' for field '{field_name}'",
                        "suggestion": f"Use one of: {', '.join(allowed_names)}" if allowed_names else "Create version first"
                    }
            
            elif value_type == "build":
                # Build field - validate against available builds
                allowed_values = self.get_custom_field_allowed_values(project_id, field_name)
                allowed_names = [v.get("name", "") for v in allowed_values if isinstance(v, dict)]
                if str(field_value) not in allowed_names:
                    return {
                        "valid": False,
                        "error": f"Invalid build '{field_value}' for field '{field_name}'",
                        "suggestion": f"Use one of: {', '.join(allowed_names)}" if allowed_names else "Create build first"
                    }
            
            elif value_type == "period":
                # Period field - validate format (e.g., "4h", "30m", "1h45m")
                import re
                period_pattern = r'^\d+[mhwd]$|^\d+h\d+m$'  # Simple pattern for periods
                if not re.match(period_pattern, str(field_value)):
                    return {
                        "valid": False,
                        "error": f"Invalid period format '{field_value}' for field '{field_name}'",
                        "suggestion": "Use format like '4h', '30m', '1h45m', or '2d'"
                    }
            
            elif value_type == "integer":
                # Integer field - validate that value can be converted to int
                try:
                        int(field_value)
                except (ValueError, TypeError):
                    return {
                        "valid": False,
                        "error": f"Invalid integer value '{field_value}' for field '{field_name}'",
                        "suggestion": "Provide a valid integer number"
                    }
            
            elif value_type == "float":
                # Float field - validate that value can be converted to float
                try:
                        float(field_value)
                except (ValueError, TypeError):
                    return {
                        "valid": False,
                        "error": f"Invalid float value '{field_value}' for field '{field_name}'",
                        "suggestion": "Provide a valid decimal number"
                    }
            
            # Multi-value field validation (if applicable, after type-specific)
            if field_schema.get("multi_value", False) and not isinstance(field_value, list):
                return {
                    "valid": False,
                    "error": f"Field '{field_name}' expects multiple values (array)",
                    "suggestion": "Provide value as an array, e.g., ['value1', 'value2']"
                }
            
            # If we reach here, validation passed
            return {
                "valid": True,
                "field": field_name,
                "value": field_value,
                "message": "Valid"
            }
            
        except Exception as e:
            logger.error(f"Error validating field '{field_name}': {str(e)}")
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}",
                "suggestion": "Check field configuration and API connectivity"
            }
