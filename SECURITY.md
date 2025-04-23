# Security Implementation

## Authentication & Authorization

### 401 Unauthorized
Returned when:
- Invalid or missing JWT token
- Token has expired
- User not found in database
- User account is inactive (`is_active = False`)

**Examples:**
- Missing `Authorization: Bearer <token>` header
- Invalid token format or signature
- Token contains non-existent user ID
- User account has been deactivated

### 403 Forbidden
Returned when:
- Valid token but insufficient permissions
- User lacks required role for the operation
- User tries to access resources they don't own

**Examples:**
- Patient tries to create doctor availability
- Non-admin tries to create users with doctor/admin roles
- User tries to access another user's private data

## Role-Based Access Control (RBAC)

### User Roles
- **PATIENT**: Can book appointments, view own data
- **DOCTOR**: Can manage availability, view own appointments
- **ADMIN**: Full system access, can create/manage all users

### Role Restrictions

#### User Creation
- **Admin-only**: Creating users with `doctor` or `admin` roles
- **Self-registration**: Patients can register via `/auth/signup/patient` (role forced to `patient`)

#### Email Validation
- All signup endpoints use `EmailStr` validation
- Duplicate email addresses are rejected
- Email format is validated by Pydantic

#### Active User Checks
- All authenticated endpoints check `is_active` status
- Inactive users receive 401 Unauthorized
- Services validate user activity before operations
- Admin access to inactive users is logged for audit

## Security Headers
- `WWW-Authenticate: Bearer` on 401 responses
- `X-Request-ID` for request tracing
- Proper CORS configuration

## Rate Limiting
- Appointment booking: 5 requests per minute per user
- Redis-based sliding window algorithm
- 429 Too Many Requests with retry information

## Logging & Monitoring
- All security events are logged with context
- Failed authentication attempts
- Permission denied events
- Admin access to inactive users
- Request tracing with user context
