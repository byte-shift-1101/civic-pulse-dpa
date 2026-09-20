# CivicPulse --- Smart Civic Complaint & Issue Management System

## Technical and Product Specification

-   **Hackathon:** DPA Hackathon 2026 --- Stage 2
-   **Case Study:** Smart Civic Complaint & Issue Management System
-   **Submission deadline:** 18 September 2026, EOD
-   **Document purpose:** Single source of truth for the product,
    architecture, workflows, APIs, data model, AI components,
    prioritization, analytics, and implementation scope.
-   **Primary implementation language:** Python
-   **Backend:** FastAPI
-   **Database:** SQLite
-   **Frontend:** React + TypeScript, delivered as a Progressive Web App
    (PWA)
-   **AI/LLM:** Groq API
-   **Voice:** Vapi or another compliant telephony provider if
    Vapi/Twilio cannot provision the required Indian number
-   **Maps/geocoding:** A production map/geocoding provider with an
    abstracted provider interface
-   **Authentication:** Phone-number OTP for registered users; anonymous
    complaint mode supported
-   **Storage:** SQLite for structured data; object storage for
    images/audio/transcripts where required

------------------------------------------------------------------------

# 1. Product Definition

## 1.1 Product name

-   **CivicPulse**
-   A multi-channel civic issue reporting and municipal operations
    platform.
-   The system connects:
    -   Citizens
    -   Municipal operators
    -   Field workers/departments
    -   Automated classification and prioritization
    -   Geographic issue intelligence
    -   Public/local complaint discovery

## 1.2 Core problem

-   Citizens may encounter:
    -   Potholes
    -   Garbage accumulation
    -   Broken street lights
    -   Drainage/waterlogging
    -   Damaged public infrastructure
    -   Road and traffic issues
    -   Public sanitation problems
    -   Other municipal service issues
-   Existing reporting processes can be fragmented across:
    -   Phone calls
    -   Web forms
    -   Apps
    -   Department-specific systems
-   Repeated reports for the same physical problem can create duplicate
    work.
-   Administrators need a consolidated view of:
    -   What is happening
    -   Where it is happening
    -   How long it has remained unresolved
    -   How many citizens are affected
    -   Which department owns it
    -   Which issues require immediate attention

## 1.3 Product objective

-   Provide one complaint lifecycle from citizen report to municipal
    resolution:
    -   Report
    -   Validate
    -   Classify
    -   Locate
    -   Deduplicate/club
    -   Prioritize
    -   Assign
    -   Work
    -   Update
    -   Resolve
    -   Verify/close
-   Make reporting possible through:
    -   PWA/web
    -   Voice helpline
-   Convert unstructured citizen input into structured municipal work
    items.
-   Give administrators geographic and operational intelligence instead
    of only a list of tickets.

------------------------------------------------------------------------

# 2. Hackathon Requirement Compliance

## 2.1 Mandatory requirements

-   Citizen complaint submission:
    -   Category
    -   Description
    -   Location
    -   Priority
-   Admin status lifecycle:
    -   `NEW`
    -   `ASSIGNED`
    -   `IN_PROGRESS`
    -   `RESOLVED`
-   FastAPI backend for:
    -   Complaint submission
    -   Assignment
    -   Status management
    -   Comments
    -   Analytics
-   SQLite preferred:
    -   Use SQLite
-   Rule-based prioritization:
    -   Complaint age
    -   Issue category
    -   Number of similar complaints
-   NYC Service Request Database:
    -   Use as an optional demonstration/training/analytics dataset.
-   AI:
    -   Optional
    -   Use for classification, summarization, location/category
        extraction.
-   Submission:
    -   Demonstrate solution
    -   Demonstrate key functionality
    -   Explain technical approach
    -   Demonstrate analytics

## 2.2 Explicit implementation mapping

-   Category:
    -   Citizen selects a category or AI proposes one.
-   Description:
    -   Text field or voice transcript.
-   Location:
    -   GPS/map pin/address/manual location.
-   Priority:
    -   Citizen may indicate perceived urgency.
    -   System computes operational priority independently.
-   Status:
    -   Strict state machine matching the required four stages.
-   Similar complaints:
    -   Geographic proximity + category + semantic similarity.
-   Comments:
    -   Citizen-visible and internal admin comments are separated.
-   Analytics:
    -   Complaint volume
    -   Status distribution
    -   Resolution time
    -   Category trends
    -   Geographic clusters
    -   Priority distribution
    -   Department workload

------------------------------------------------------------------------

# 3. Stakeholders

## 3.1 Citizen

-   Reports a civic issue.
-   Can submit:
    -   Text
    -   Location
    -   Image
    -   Voice call
-   Can:
    -   Track complaints
    -   View nearby public complaints
    -   Upvote an existing complaint
    -   Receive updates
    -   Add follow-up information
    -   See resolution information
-   May report anonymously.

## 3.2 Municipal operator

-   Reviews incoming complaints.
-   Corrects classification when necessary.
-   Assigns complaints to departments/operators.
-   Changes status.
-   Adds comments.
-   
-   Reviews map clusters.
-   Monitors SLA/aging.

## 3.3 Department/field worker

-   Receives assigned work.
-   Views:
    -   Description
    -   Location
    -   Images
    -   Related complaints
    -   Priority
-   Updates progress.
-   Adds work notes/evidence.
-   Marks work as ready for resolution.

## 3.4 Municipal administrator

-   Manages:
    -   Categories
    -   Departments
    -   Users/roles
    -   Priority rules
    -   SLA thresholds
-   Views city/regional analytics.
-   Reviews unresolved clusters and workload.

## 3.5 System/AI services

-   Classify complaints.
-   Extract structured fields.
-   Summarize long descriptions/transcripts.
-   Find similar complaints.
-   Detect geographic clusters.
-   Generate priority signals.
-   Never directly override the required municipal status workflow
    without an auditable human/system action.

------------------------------------------------------------------------

# 4. Product Surfaces

## 4.1 Citizen PWA

### Home

-   Location-aware regional feed.
-   Nearby open complaints.
-   Search.
-   Category filters.
-   Status filters.
-   Sort:
    -   Trending
    -   Newest
    -   Oldest
    -   Highest community support
    -   Highest operational priority
-   `Report an Issue` CTA.
-   `Call Helpline` CTA.

### Report issue

-   Step 1: Issue category.
-   Step 2: Description.
-   Step 3: Location.
-   Step 4: Optional image.
-   Step 5: Optional citizen priority/urgency.
-   Step 6: Duplicate suggestions.
-   Step 7: Submit.
-   Return:
    -   Complaint ID
    -   Current status
    -   Initial priority
    -   Department/category
    -   Estimated workflow/SLA information where configured.

### Duplicate prevention

-   Before creating a new complaint:
    -   Search nearby complaints.
    -   Search semantically similar complaints.
-   If strong matches exist:
    -   Show existing complaints.
    -   Allow user to upvote/follow an existing complaint.
    -   Allow `Report separately` if the issue is materially different.

### Complaint details

-   Complaint ID.
-   Category.
-   Description/summary.
-   Location map.
-   Created time.
-   Status timeline.
-   Priority.
-   Upvotes/support count.
-   Related/clubbbed complaint count.
-   Public updates.
-   Optional resolution evidence.
-   Follow/subscribe.
-   Add follow-up comment/photo where allowed.

### My complaints

-   List of complaints created/followed by the citizen.
-   Status.
-   Priority.
-   Last update.
-   Complaint age.
-   Search/filter.

### Notifications

-   Complaint assigned.
-   Status changed.
-   Admin response/comment.
-   Complaint clubbed/merged.
-   Resolution submitted.
-   Complaint closed.
-   Notification channels:
    -   PWA push
    -   SMS where configured
    -   In-app notification

------------------------------------------------------------------------

# 5. Voice Helpline

## 5.1 Purpose

-   Provide a low-friction reporting channel for citizens who:
    -   Have limited digital access
    -   Prefer speaking
    -   Have no usable mobile data
    -   Need accessibility support
-   Important distinction:
    -   The phone channel can work without the citizen having internet
        access.
    -   It still requires cellular/PSTN connectivity and backend
        telephony connectivity.
    -   It is not an offline system in the literal sense.

## 5.2 Call workflow

1.  Citizen calls civic helpline.
2.  Telephony provider connects call to voice agent.
3.  Voice agent:
    -   Greets citizen.
    -   Explains that the call is for non-emergency civic issues.
    -   Collects description.
    -   Asks category questions when required.
    -   Collects location.
    -   Asks for urgency.
    -   Confirms extracted information.
4.  Transcript is sent to backend.
5.  Backend:
    -   Stores call metadata.
    -   Stores transcript or secure reference.
    -   Runs classification/extraction.
    -   Searches similar complaints.
    -   Generates structured complaint.
6.  Citizen hears:
    -   Complaint summary.
    -   Complaint ID.
    -   Next step.
7.  Complaint enters normal workflow.

## 5.3 Location from voice

-   Preferred:
    -   Ask for address/landmark.
    -   Geocode it.
-   If the caller is using a registered phone:
    -   Do not assume phone location unless a compliant location service
        explicitly provides it.
-   If location cannot be confidently resolved:
    -   Create `LOCATION_PENDING`.
    -   Queue for operator verification.
-   AI-extracted coordinates must never be treated as ground truth
    without validation.

## 5.4 Voice failure handling

-   If speech is unclear:
    -   Ask the user to repeat.
-   If category is uncertain:
    -   Ask a constrained follow-up.
-   If location is uncertain:
    -   Ask for nearby landmark/street.
-   If AI fails:
    -   Store transcript and route to human review.
-   If call disconnects:
    -   Persist partial transcript if available.
    -   Do not create a complaint until minimum required fields are
        available.
    -   If enough information exists, create `PENDING_REVIEW`.

## 5.5 Telephony implementation constraint

-   Vapi supports inbound/outbound voice agents and can integrate with
    external systems.
-   Vapi documentation states that custom/international numbers can be
    imported through Twilio.
-   However, Twilio's current documentation says it does not offer local
    or mobile Indian phone numbers.
-   Therefore:
    -   Do not make `Twilio + Vapi + Indian local number` a hard
        production dependency.
    -   Abstract telephony behind `TelephonyProvider`.
    -   For the hackathon demo, use an available compliant
        number/provider.
    -   For an Indian deployment, select a compliant Indian telephony
        provider or approved SIP/voice integration.
-   This keeps the product architecture stable even if the telephony
    vendor changes.

------------------------------------------------------------------------

# 6. Authentication and Identity

## 6.1 Registered user

-   Phone number is the primary identity.
-   OTP verification.
-   Session/JWT after successful verification.
-   Minimal profile:
    -   User ID
    -   Phone number
    -   Optional display name
    -   Notification preferences
-   Do not expose phone numbers publicly.

## 6.2 Anonymous complaint

-   Citizen can submit without creating a persistent account.
-   System creates an anonymous reporter ID.
-   Complaint can still be tracked using:
    -   One-time complaint tracking token
    -   Optional verified phone if supplied
-   Anonymous users cannot access private account history unless they
    later link the complaint through a secure token/verification
    process.

## 6.3 Upvote abuse prevention

-   One active vote per authenticated user per complaint.
-   Anonymous users:
    -   Either cannot upvote, or receive a signed temporary voter token.
-   Rate-limit repeated voting.
-   Detect suspicious vote bursts.
-   Never expose exact personal identities through public feeds.

------------------------------------------------------------------------

# 7. Complaint Lifecycle

## 7.1 Required state machine

``` text
NEW
  |
  v
ASSIGNED
  |
  v
IN_PROGRESS
  |
  v
RESOLVED
```

## 7.2 Allowed transitions

-   `NEW -> ASSIGNED`
    -   Complaint assigned to department/operator.
-   `ASSIGNED -> IN_PROGRESS`
    -   Work accepted/started.
-   `IN_PROGRESS -> RESOLVED`
    -   Work completed and resolution recorded.

## 7.3 Controlled exception transitions

-   `ASSIGNED -> NEW`
    -   Only when assignment is explicitly removed.
-   `IN_PROGRESS -> ASSIGNED`
    -   Only for reassignment.
-   `IN_PROGRESS -> NEW`
    -   Not preferred; require administrator action and audit reason.
-   `RESOLVED -> IN_PROGRESS`
    -   Reopen only through an explicit `reopen` action.
    -   Store reason and actor.
-   The public-facing lifecycle remains the four required stages.

## 7.4 Resolution

-   Resolution requires:
    -   Resolution note
    -   Timestamp
    -   Actor
-   Optional:
    -   Before/after image
    -   Field worker note
    -   External work-order reference
-   Citizen receives resolution notification.
-   Optional citizen confirmation:
    -   `Resolved`
    -   `Still an issue`
-   A negative confirmation can reopen the complaint or create a
    follow-up ticket depending on admin policy.

------------------------------------------------------------------------

# 8. Complaint Data Model

## 8.1 Complaint document

``` text
Complaint
- id
- public_id
- reporter_id
- reporter_visibility: anonymous | private | public
- source: web | pwa | voice | admin
- description_original
- description_summary
- category_id
- category_confidence
- citizen_priority
- system_priority
- priority_score
- priority_explanation[]
- status
- department_id
- assignee_id
- location
    - type: Point
    - coordinates: [longitude, latitude]
    - address
    - landmark
    - geocoding_confidence
- created_at
- assigned_at
- started_at
- resolved_at
- last_updated_at
- upvote_count
- follower_count
- - - - media_ids[]
- public_comment_ids[]
- internal_comment_ids[]
- ai_metadata
- audit_metadata
```

## 8.2 Category

``` text
Category
- id
- name
- description
- department_id
- base_priority_weight
- sla_hours
- active
```

## 8.3 Department

``` text
Department
- id
- name
- service_area
- categories[]
- active
```

## 8.4 User

``` text
User
- id
- phone_hash
- phone_encrypted
- display_name
- role
- verified
- notification_preferences
- created_at
- last_login_at
```

## 8.5 Comment

``` text
Comment
- id
- complaint_id
- author_id
- author_role
- visibility: public | internal
- text
- media_ids[]
- created_at
```

## 8.6 Audit event

``` text
AuditEvent
- id
- complaint_id
- actor_id
- actor_role
- action
- old_value
- new_value
- reason
- timestamp
```

------------------------------------------------------------------------

# 9. Location Architecture

## 9.1 Location inputs

-   Browser/device GPS.
-   Map pin.
-   Address search.
-   Landmark.
-   Voice-extracted address.
-   Manual latitude/longitude for admin.
-   Dataset-provided coordinates.

## 9.2 Canonical representation

-   Store complaint location as latitude/longitude coordinates:
    -   `Point`
    -   `[longitude, latitude]`
-   SQLite `R-Tree/spatial indexing where required` index on location.
-   Enables:
    -   Nearby search
    -   Radius filtering
    -   Cluster queries
    -   Map bounding-box queries
    -   Nearest complaint lookup

## 9.3 Search radius

-   Citizen nearby feed:
    -   Default configurable radius, e.g. 5 km.
-   Regional feed:
    -   Configurable.
-   Hackathon product constraint:
    -   Maximum user-visible search radius = 50 km.
-   Admin:
    -   Can inspect the full configured service region.

## 9.4 Location confidence

``` text
HIGH
- Device GPS
- Exact geocoded address

MEDIUM
- Reliable address/landmark geocode

LOW
- Ambiguous landmark
- AI-only inferred location
```

-   Low-confidence location:
    -   Flag for verification.
    -   Do not use as a high-confidence cluster anchor.

------------------------------------------------------------------------

# 10. AI Architecture

## 10.1 AI principle

-   AI assists municipal operations.
-   Deterministic business rules remain responsible for:
    -   Required status transitions
    -   Priority formula
    -   Authentication
    -   Authorization
    -   Audit logs
-   AI outputs are structured, validated, and confidence-scored.

## 10.2 AI tasks

### Classification

-   Input:
    -   Complaint text/transcript
-   Output:
    -   Category
    -   Confidence
-   Example:
    -   `pothole`
    -   `garbage`
    -   `street_light`
    -   `drainage`
    -   `waterlogging`
    -   `road_damage`

### Summarization

-   Input:
    -   Long citizen description
    -   Voice transcript
-   Output:
    -   1--3 sentence operational summary.
-   Preserve original text.

### Extraction

-   Extract:
    -   Category
    -   Address
    -   Landmark
    -   Street
    -   Locality
    -   Urgency indicators
-   Return structured JSON.

### Relevant complaint discovery

-   Do not ask an LLM to search the entire database directly.
-   Pipeline:
    1.  Geospatial candidate retrieval.
    2.  Category filtering.
    3.  Text/semantic similarity.
    4.  Optional LLM verification.
    5.  Human review for uncertain clubbing.

### Agent

-   The agent is a workflow orchestrator, not an unrestricted autonomous
    administrator.
-   Allowed tools:
    -   `search_nearby_complaints`
    -   `search_similar_complaints`
    -   `lookup_categories`
    -   `geocode_location`
    -   `create_draft_complaint`
    -   `request_missing_field`
    -   `summarize_complaint`
-   The agent cannot:
    -   Change arbitrary complaint status
    -   Delete complaints
    -   Alter audit logs
    -   Modify priority rules
    -   Assign itself elevated permissions

## 10.3 Groq

-   Use Groq for low-latency LLM inference.
-   Keep provider behind an `LLMProvider` interface.
-   This permits model/provider changes without changing product logic.

------------------------------------------------------------------------

# 11. Rule-Based Prioritization

## 11.1 Important distinction

-   `Citizen priority`:
    -   What the citizen says about urgency.
-   `System priority`:
    -   Computed operational score.
-   Citizen priority must not directly determine final operational
    priority.

## 11.2 Required signals

-   Complaint age.
-   Issue category.
-   Number of similar complaints.

## 11.3 Additional product signals

-   Upvotes.
-   Location cluster density.
-   Safety-critical category.
-   Current status.
-   SLA breach/approaching breach.

## 11.4 Proposed score

``` text
priority_score =
    W_age * age_score
  + W_category * category_score
  + W_similar * similar_complaint_score
  + W_upvotes * upvote_score
  + W_cluster * cluster_density_score
```

-   Normalize every component to `[0, 100]`.
-   Weights are configurable.
-   Suggested initial weights:
    -   Age: 25%
    -   Category: 30%
    -   Similar complaints: 20%
    -   Upvotes: 15%
    -   Cluster density: 10%
-   The exact weights are configuration, not hard-coded assumptions.

## 11.5 Age score

``` text
age_score = min(100, hours_open / AGE_SATURATION_HOURS * 100)
```

## 11.6 Category score

-   Maintain an administrator-configurable priority table.
-   Example:
    -   Public safety hazard: 100
    -   Major road obstruction: 90
    -   Waterlogging/drainage: 80
    -   Street light: 60
    -   Garbage: 55
    -   Cosmetic issue: 30
-   Final category values should be configured for the municipality
    rather than presented as universal truth.

## 11.7 Similar complaint score

``` text
similar_score = min(100, similar_count / SIMILAR_SATURATION * 100)
```

## 11.8 Upvote score

-   Use diminishing returns so a large neighborhood does not overwhelm
    all other signals.

``` text
upvote_score = min(100, log1p(upvotes) / log1p(UPVOTE_SATURATION) * 100)
```

## 11.9 Priority bands

-   `CRITICAL`

-   `HIGH`

-   `MEDIUM`

-   `LOW`

-   Bands are generated from score thresholds.

-   Thresholds are configurable.

-   Show the explanation to administrators:

    -   `+32 age`
    -   `+27 category`
    -   `+15 similar reports`
    -   `+8 upvotes`
    -   `+5 cluster`

------------------------------------------------------------------------

# 12. Complaint Clustering and Clubbing

## 12.1 Objective

-   Prevent 50 citizens reporting the same pothole from producing 50
    independent work items.
-   Preserve citizen participation while creating one operational issue.

## 12.2 Candidate retrieval

-   Retrieve complaints:
    -   Within configurable geographic radius.
    -   Same/related category.
    -   Open or recently resolved.
-   Apply text similarity.
-   Rank candidates.

## 12.3 Clubbing decision

-   `High confidence`:
    -   Suggest automatic clubbing.
-   `Medium confidence`:
    -   Ask admin for confirmation.
-   `Low confidence`:
    -   Keep separate.

## 12.4 Club structure

-   One `parent complaint` becomes the operational issue.
-   Related citizen reports become:
    -   Supporting reports
    -   Additional evidence
    -   Upvotes/support
-   Every contributor can still see their original complaint
    relationship.

## 12.5 Geographic clusters

-   Use:
    -   Grid/geohash buckets for simple real-time density.
    -   DBSCAN/HDBSCAN or similar clustering for analytics.
-   Cluster dimensions:
    -   Latitude/longitude
    -   Category
    -   Time window
-   Example:
    -   `8 road complaints within 700 m during 48 hours`.

------------------------------------------------------------------------

# 13. Admin Portal

## 13.1 Dashboard

-   KPI cards:
    -   Total open
    -   New today
    -   Assigned
    -   In progress
    -   Resolved
    -   SLA-breached
-   Priority queue.
-   Regional heatmap.
-   Category distribution.
-   Resolution-time chart.
-   Complaint trend over time.

## 13.2 Complaint queue

-   Columns:
    -   Public ID
    -   Category
    -   Summary
    -   Location
    -   Age
    -   Priority
    -   Similar count
    -   Upvotes
    -   Status
    -   Department
    -   Assignee
-   Sort:
    -   Priority
    -   Age
    -   Similar complaints
    -   Upvotes
    -   Created time
-   Filter:
    -   Category
    -   Department
    -   Status
    -   Priority
    -   Time range
    -   Geographic region

## 13.3 Complaint detail

-   Full original report.
-   AI summary.
-   AI classification and confidence.
-   Location map.
-   Images.
-   Related complaints.
-   Cluster information.
-   Priority breakdown.
-   Timeline.
-   Public comments.
-   Internal notes.
-   Assignment controls.
-   Status controls.
-   Audit history.

## 13.4 Assignment

-   Assign:
    -   Department
    -   Operator/worker
-   Reassignment:
    -   Require reason.
-   Show current workload of assignees.

## 13.5 Map operations

-   Map layers:
    -   Open complaints
    -   Resolved complaints
    -   Priority
    -   Category
    -   Density clusters
    -   SLA breaches
-   Click cluster:
    -   Show aggregate.
    -   Expand into complaints.
-   Click complaint:
    -   Open detail.

## 13.6 Analytics

-   Volume by:
    -   Day/week/month
    -   Category
    -   Region
    -   Source
-   Status funnel.
-   Median and average resolution time.
-   Age buckets.
-   SLA compliance.
-   Top recurring locations.
-   Top complaint categories.
-   Cluster growth.
-   Department workload.
-   AI classification confidence/error review.

------------------------------------------------------------------------

# 14. Regional Complaint Feed

## 14.1 Purpose

-   Let citizens see that an issue is already known.
-   Encourage support instead of duplicate submissions.
-   Improve visibility of local problems.

## 14.2 Ranking

``` text
regional_score =
    community_support
  + time_signal
  + operational_priority
```

-   Do not use raw upvotes alone.
-   Apply time decay to avoid permanently promoting old issues.

## 14.3 Visibility rules

-   Public complaint summary is visible.
-   Reporter identity is hidden unless explicitly public.
-   Exact residential coordinates may be generalized for
    privacy-sensitive categories.
-   Internal notes are never public.

------------------------------------------------------------------------

# 15. Notifications

## 15.1 Events

-   Complaint created.
-   Complaint assigned.
-   Status changed.
-   Comment added.
-   Complaint clubbed.
-   Resolution submitted.
-   Complaint reopened.
-   SLA breach.

## 15.2 Delivery

-   In-app notification.
-   PWA push notification.
-   SMS where configured.
-   Voice callback only as an optional future feature.

## 15.3 Notification preferences

-   Citizen can choose:
    -   Push
    -   SMS
    -   Both
    -   Critical-only

------------------------------------------------------------------------

# 16. Backend Architecture

## 16.1 High-level architecture

``` text
Citizen PWA
    |
    v
API Gateway / FastAPI
    |
    +------------------ Authentication
    |
    +------------------ Complaint Service
    |
    +------------------ Comment Service
    |
    +------------------ Assignment Service
    |
    +------------------ Status Workflow
    |
    +------------------ Prioritization Engine
    |
    +------------------ Similarity / Clubbing Service
    |
    +------------------ Notification Service
    |
    +------------------ Analytics Service
    |
    +------------------ AI Orchestrator
    |                      |
    |                      +---- Groq
    |
    +------------------ Geocoding/Maps Adapter
    |
    +------------------ Telephony Adapter
    |                      |
    |                      +---- Vapi / compliant provider
    |
    v
SQLite
    |
    +---- complaints
    +---- users
    +---- categories
    +---- departments
    +---- comments
    +---- notifications
    +---- audit_events
    +---- clusters
```

## 16.2 Backend modules

``` text
backend/
  app/
    main.py
    config.py
    api/
      auth.py
      complaints.py
      comments.py
      assignments.py
      analytics.py
      maps.py
      notifications.py
      admin.py
      voice.py
    models/
      complaint.py
      user.py
      category.py
      department.py
      comment.py
      notification.py
      audit.py
    services/
      complaint_service.py
      priority_service.py
      similarity_service.py
      clustering_service.py
      assignment_service.py
      notification_service.py
      analytics_service.py
      geocoding_service.py
      ai_service.py
      voice_service.py
    repositories/
    middleware/
    workers/
    tests/
```

------------------------------------------------------------------------

# 17. API Specification

## 17.1 Authentication

``` text
POST /api/v1/auth/request-otp
POST /api/v1/auth/verify-otp
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

## 17.2 Complaints

``` text
POST   /api/v1/complaints
GET    /api/v1/complaints
GET    /api/v1/complaints/{id}
PATCH  /api/v1/complaints/{id}
DELETE /api/v1/complaints/{id}
```

## 17.3 Citizen actions

``` text
POST /api/v1/complaints/{id}/upvote
DELETE /api/v1/complaints/{id}/upvote
POST /api/v1/complaints/{id}/follow
DELETE /api/v1/complaints/{id}/follow
POST /api/v1/complaints/{id}/comments
```

## 17.4 Existing complaint discovery

``` text
GET /api/v1/complaints/relevant

```

## 17.5 Admin

``` text
POST  /api/v1/admin/complaints/{id}/assign
POST  /api/v1/admin/complaints/{id}/status
POST  /api/v1/admin/complaints/{id}/reopen
POST  /api/v1/admin/complaints/{id}/merge
GET   /api/v1/admin/queue
GET   /api/v1/admin/analytics
GET   /api/v1/admin/audit/{complaint_id}
```

## 17.6 Voice

``` text
POST /api/v1/webhooks/voice
POST /api/v1/webhooks/voice/transcript
POST /api/v1/voice/complaint-draft
```

## 17.7 Maps

``` text
GET /api/v1/map/complaints
GET /api/v1/map/clusters
GET /api/v1/map/nearby
```

## 17.8 API standards

-   REST/JSON.
-   Versioned API:
    -   `/api/v1/...`
-   Pydantic request/response schemas.
-   Automatic OpenAPI documentation.
-   Pagination on all collection endpoints.
-   Rate limiting.
-   Request IDs for tracing.
-   Structured error responses.

------------------------------------------------------------------------

# 18. Security and Privacy

## 18.1 Authentication

-   OTP.
-   Short-lived access token.
-   Refresh token where required.
-   Admin authentication must use stronger controls in production.

## 18.2 Authorization

-   RBAC:
    -   Citizen
    -   Operator
    -   Department manager
    -   Admin
-   Every admin endpoint checks role.

## 18.3 PII

-   Phone numbers:
    -   Encrypted at rest.
    -   Hashed representation for lookup where practical.
-   Never expose phone numbers in public APIs.
-   Avoid storing unnecessary personal information.

## 18.4 Media

-   Store images outside SQLite when practical.
-   Database stores:
    -   Object key
    -   MIME type
    -   Size
    -   Upload time
-   Validate:
    -   File type
    -   File size
    -   Malware/security policy

## 18.5 AI privacy

-   Do not send unnecessary PII to LLM APIs.
-   Redact phone numbers and sensitive personal details before LLM
    processing.
-   Store AI inputs/outputs only according to retention policy.

## 18.6 Auditability

-   Every privileged action creates an audit event.
-   Audit events are append-only from the application perspective.

------------------------------------------------------------------------

# 19. Reliability and Error Handling

## 19.1 External service failure

-   LLM unavailable:
    -   Complaint still gets created.
    -   Manual classification queue.
-   Geocoder unavailable:
    -   Store address.
    -   Location remains pending.
-   Notification provider unavailable:
    -   Queue notification.
-   Telephony provider unavailable:
    -   Web/PWA remains operational.
-   Maps unavailable:
    -   Complaint creation remains operational.

## 19.2 Idempotency

-   Complaint creation supports idempotency key.
-   Webhooks are idempotent.
-   Repeated telephony webhook events must not create duplicate
    complaints.

## 19.3 Background jobs

-   Use a worker/queue for:
    -   AI classification
    -   Similarity search
    -   Cluster recomputation
    -   Notifications
    -   Analytics aggregation
-   Hackathon MVP may use a lightweight background task mechanism.
-   Production should use Redis + worker infrastructure or equivalent.

------------------------------------------------------------------------

# 20. Observability

-   Application logs:
    -   JSON structured logs.
-   Metrics:
    -   API latency
    -   Error rate
    -   AI latency
    -   AI failure rate
    -   Complaint creation rate
    -   Notification success rate
-   Tracing:
    -   Request ID propagated across services.
-   Health:
    -   `/health`
    -   `/ready`
-   Admin monitoring:
    -   Failed AI jobs
    -   Pending location verification
    -   Pending duplicate review

------------------------------------------------------------------------

# 21. Database Indexes

## 21.1 Required

-   `complaints.location: R-Tree/spatial indexing where required`
-   `complaints.status`
-   `complaints.category_id`
-   `complaints.created_at`
-   `complaints.priority_score`
-   `complaints.department_id`
-   `complaints.duplicate_group_id`

## 21.2 Compound indexes

-   `(status, priority_score, created_at)`
-   `(category_id, status, created_at)`
-   `(department_id, status, priority_score)`

------------------------------------------------------------------------

# 22. Dataset / Demo Data

## 22.1 NYC 311 dataset

-   The NYC311 system publishes service-request data and describes
    service requests as requests for the city to provide a service or
    address a problem.
-   Use the dataset for:
    -   Seed data
    -   Map visualization
    -   Trend analysis
    -   Testing prioritization
    -   Demonstrating clusters
-   Do not claim that the dataset represents the target municipality.

## 22.2 Demo strategy

-   Import a manageable sample.
-   Normalize:
    -   Complaint category
    -   Location
    -   Created time
    -   Status
    -   Agency/department
-   Generate synthetic fields only where the original dataset lacks
    fields required for the demo.
-   Clearly label synthetic fields in the demo.

------------------------------------------------------------------------

# 23. End-to-End Use Cases

## 23.1 Citizen reports pothole through PWA

1.  Open PWA.
2.  Location permission granted.
3.  Select `Road/Pothole`.
4.  Add description.
5.  Add photo.
6.  Location automatically captured.
7.  System searches nearby complaints.
8.  Existing matching complaint appears.
9.  Citizen can:
    -   Upvote existing issue, or
    -   Submit separate issue.
10. Complaint created.
11. Priority engine runs.
12. Department selected.
13. Admin sees complaint in queue.
14. Admin assigns.
15. Worker starts.
16. Status becomes `IN_PROGRESS`.
17. Work is completed.
18. Admin/worker records resolution.
19. Status becomes `RESOLVED`.
20. Citizen receives notification.

## 23.2 Citizen has no mobile data

1.  Citizen calls helpline.
2.  Voice agent collects complaint.
3.  Caller provides location verbally.
4.  Transcript reaches backend.
5.  AI extracts fields.
6.  Geocoder resolves location.
7.  Complaint is created.
8.  Citizen receives complaint ID verbally.
9.  Same admin workflow applies.

## 23.3 Many citizens report same issue

1.  First report creates complaint.
2.  Additional users submit similar reports.
3.  Candidate search finds existing complaint.
4.  UI recommends supporting the existing issue.
5.  If submitted separately, similarity service detects relationship.
6.  Admin confirms clubbing when needed.
7.  One operational complaint represents the physical issue.
8.  Supporting reports increase evidence/community support.

## 23.4 Admin sees geographic outbreak

1.  Admin opens map.
2.  Heatmap shows high-density region.
3.  Cluster contains multiple similar complaints.
4.  Admin opens cluster.
5.  System shows:
    -   Number of complaints
    -   Category
    -   Time range
    -   Average age
    -   Priority
6.  Admin can assign a consolidated work item.

------------------------------------------------------------------------

# 24. Non-Functional Requirements

## 24.1 Performance

-   Standard API response target:
    -   p95 \< 500 ms excluding external AI/geocoding calls.
-   Complaint creation:
    -   Persist immediately.
    -   AI enrichment can be asynchronous.
-   Map queries:
    -   Paginated/clustered.
    -   Never return thousands of individual markers by default.

## 24.2 Availability

-   Citizen reporting should continue even if AI is unavailable.
-   Core complaint database is the system of record.

## 24.3 Accessibility

-   Mobile-first.
-   Keyboard accessible.
-   High-contrast UI.
-   Screen-reader-friendly labels.
-   Large touch targets.
-   Voice channel for users unable/unwilling to use the PWA.

## 24.4 Localization

-   Category and UI strings must be externalized.
-   Voice agent should support selected local languages.
-   AI should preserve original complaint language and generate
    structured English fields if needed.

------------------------------------------------------------------------

# 25. MVP vs Future Scope

## 25.1 Hackathon MVP

-   PWA citizen interface.
-   Phone OTP login.
-   Anonymous reporting.
-   Complaint creation.
-   Map location.
-   Image upload.
-   Required four-status lifecycle.
-   Admin dashboard.
-   Assignment.
-   Comments.
-   Rule-based priority.
-   Nearby duplicate detection.
-   AI classification.
-   AI summary.
-   AI location/category extraction.
-   Heatmap.
-   Basic clustering.
-   Regional feed.
-   Upvotes.
-   Voice helpline demo.
-   Analytics.
-   NYC dataset import.

## 25.2 Future

-   Full field-worker application.
-   Offline-first complaint drafts.
-   Multilingual voice.
-   Municipal work-order integrations.
-   Automated SLA escalation.
-   Advanced semantic embeddings.
-   Predictive maintenance.
-   Infrastructure asset registry.
-   Computer vision for image-based issue classification.
-   Cross-department routing.
-   Public transparency dashboard.
-   Advanced anomaly detection.

------------------------------------------------------------------------

# 26. Demo Script

## 26.1 Citizen path

-   Open PWA.
-   Show regional feed.
-   Search nearby complaint.
-   Submit pothole.
-   Show duplicate suggestion.
-   Submit/upvote.
-   Show complaint ID.
-   Open complaint detail.

## 26.2 AI path

-   Submit natural-language complaint.
-   Show:
    -   Original text
    -   AI category
    -   AI summary
    -   Extracted location
    -   Confidence
-   Show similar complaints.

## 26.3 Admin path

-   Open dashboard.
-   Show priority queue.
-   Open complaint.
-   Show priority explanation.
-   Show cluster.
-   Assign department.
-   Change:
    -   `NEW -> ASSIGNED`
    -   `ASSIGNED -> IN_PROGRESS`
    -   `IN_PROGRESS -> RESOLVED`
-   Add resolution note.
-   Show citizen notification.

## 26.4 Voice path

-   Call helpline.
-   Report issue verbally.
-   Show transcript arriving in backend.
-   Show structured complaint generated.
-   Show it entering the same queue.

------------------------------------------------------------------------

# 27. Technical Decisions and Corrections

## 27.1 FastAPI implies Python

-   Use Python 3.11+.
-   FastAPI is the backend framework.
-   Use Pydantic for validation.
-   Use an async SQLite-compatible Python driver.

## 27.2 SQLite over SQLite

-   SQLite selected because the product is inherently:
    -   Geospatial
    -   Document-oriented
    -   Dynamic
    -   Suitable for nested AI metadata
-   Use `R-Tree/spatial indexing where required` indexes for location.

## 27.3 Do not make AI the source of truth

-   AI is useful for:
    -   Classification
    -   Extraction
    -   Summarization
    -   Similarity assistance
-   Deterministic rules own:
    -   State transitions
    -   Priority calculation
    -   Permissions
    -   Auditability

## 27.4 "No network" clarification

-   The phone channel handles the case where a citizen has:
    -   No mobile data
    -   No app
    -   No web access
-   It does not handle complete absence of cellular/PSTN connectivity.
-   True offline submission requires:
    -   Local device storage
    -   Later synchronization
    -   Or assisted/manual intake.
-   This should not be claimed as part of the current MVP.

## 27.5 "Accurate coordinates" clarification

-   GPS coordinates are not guaranteed to be accurate.
-   Store:
    -   Coordinates
    -   Source
    -   Accuracy if device provides it
    -   Geocoding confidence
-   Allow manual correction.

## 27.6 "Priority" clarification

-   Citizen-entered urgency is a signal, not the final system priority.
-   The final priority must be explainable and rule-based to satisfy the
    case-study requirement.

------------------------------------------------------------------------

# 28. Acceptance Criteria

## Citizen

-   [ ] Can submit category.
-   [ ] Can submit description.
-   [ ] Can submit location.
-   [ ] Can optionally attach image.
-   [ ] Can see complaint ID.
-   [ ] Can track status.
-   [ ] Can view nearby complaints.
-   [ ] Can upvote.
-   [ ] Can receive updates.
-   [ ] Can submit anonymously.
-   [ ] Can submit through voice.

## Admin

-   [ ] Can see all complaints.
-   [ ] Can filter/search.
-   [ ] Can assign.
-   [ ] Can update status.
-   [ ] Can comment.
-   [ ] Can see audit trail.
-   [ ] Can see map.
-   [ ] Can see clusters.
-   [ ] Can see priority score/explanation.
-   [ ] 
-   [ ] Can see analytics.

## Backend

-   [ ] FastAPI.
-   [ ] SQLite.
-   [ ] Geospatial index.
-   [ ] Rule-based prioritization.
-   [ ] AI classification.
-   [ ] AI summarization.
-   [ ] AI extraction.
-   [ ] Relevant complaint discovery.
-   [ ] API documentation.
-   [ ] Authentication/authorization.
-   [ ] Rate limiting.
-   [ ] Error handling.
-   [ ] Webhook idempotency.

------------------------------------------------------------------------

# 29. Reference Documentation

-   FastAPI documentation: https://fastapi.tiangolo.com/
-   SQLite geospatial documentation:
    https://www.mongodb.com/docs/manual/geospatial-queries/
-   Vapi phone calling documentation: https://docs.vapi.ai/phone-calling
-   Groq documentation: https://console.groq.com/docs/overview
-   Twilio Verify documentation: https://www.twilio.com/docs/verify
-   Twilio India voice guidelines:
    https://www.twilio.com/en-us/guidelines/in/voice
-   NYC311: https://portal.311.nyc.gov/about-nyc-311/
