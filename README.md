Project Overview: Intelligent Rostering Agent
 
1. Introduction & Executive Summary
The Intelligent Rostering Agent is an automated system developed for the elder care company to address the complex and time-consuming task of assigning Member Care Assistants (MCAs) to daily Out-of-Home Assistance (OHA) service requests. Manual rostering often leads to inefficiencies, potential biases, and inconsistent service quality, especially when trying to balance member needs, MCA availability, and logistical constraints. This project implements a cloud-based, AI-driven solution that automates the assignment process, optimizing matches based on quantifiable factors like continuity of care, proximity, and language preference. The system generates a daily roster with clear justifications for each assignment, improving operational efficiency, ensuring consistency, and enhancing the overall quality of care provided to members.
2. Use Case & Problem Statement
Scheduling MCAs for daily member visits is a critical operational task. However, performing this manually presents several challenges:
Complexity: Balancing numerous factors simultaneously (member locations, specific care needs, MCA availability, travel time, leave schedules, member-MCA history, language barriers) is mentally taxing and prone to errors.
Inefficiency: Manual rostering consumes significant administrative time that could be spent on higher-value tasks like member engagement or care coordination.
Subjectivity: Decisions can sometimes be based on intuition or convenience rather than objective data, potentially leading to suboptimal assignments.
Lack of Continuity: Members often prefer seeing familiar MCAs, but ensuring this continuity manually across many assignments is difficult to track and prioritize consistently.
Scalability Issues: As the number of members and MCAs grows, the manual process becomes increasingly unmanageable.
3. Project Goal
The primary goal of this project is to automate and optimize the daily MCA rostering process. This involves creating an intelligent system that assigns the most suitable available MCA to each pending service request based on predefined, data-driven criteria, while providing transparency into the decision-making process.
4. Solution: The Intelligent Rostering Agent
The project delivers a serverless application built on Amazon Web Services (AWS) that orchestrates the entire rostering workflow. Operators can initiate the process via a natural language command (using Amazon Bedrock) or through a dedicated API endpoint. The system then automatically:
Retrieves all pending service requests for the specified date.
Identifies all MCAs available to work on that date (considering leave schedules).
Enriches this data by fetching member locations, language preferences, MCA locations, MCA languages, and the historical service count between each member-MCA pair.
Applies an intelligent matching algorithm to score each potential MCA-service pairing based on weighted criteria.
Assigns the best-scoring MCA to each service, ensuring no MCA is double-booked.
Generates a final roster in JSON format, including a detailed, human-readable justification for each assignment.
5. Key Features & Intelligence
The "intelligence" of the agent lies in its multi-factor scoring and justification system:
Continuity of Care (Weighted 30%): The system queries historical service records to count previous visits between a member and an MCA. It heavily prioritizes assigning MCAs who have served the member frequently, enhancing member comfort and familiarity.
Proximity (Weighted 50%): Using latitude/longitude data from members and MCAs, the system calculates the Haversine distance. It prioritizes assigning the geographically closest available MCA to minimize travel time and improve responsiveness.
Language Match (Weighted 20%): The system checks language preferences stored in members and MCAs. A match provides a scoring advantage, facilitating better communication and member experience.
Dynamic Justification: For each assignment, the agent generates a justification string (formatted for the frontend) that ranks the reasons for the match based on their contribution to the score (e.g., "1. Strong continuity of care with 8 previous visits", "2. Moderate distance of 5.1 km..."). If no specific criteria are met, it transparently states, "Assigned as best available option."
6. Technical Architecture
The system leverages a robust and scalable serverless architecture on AWS:
Amazon Bedrock Agent: Provides a natural language interface for operators to initiate the process.
Amazon API Gateway: Exposes RESTful endpoints (POST /rosters to start, GET /rosters/{executionArn} to poll) for frontend integration.
AWS Lambda: Hosts the individual Python functions responsible for specific tasks (getting services, getting MCAs, matching, handling API requests). These functions are designed to be efficient and interact securely with other AWS services.
AWS Step Functions: Orchestrates the multi-step asynchronous workflow, managing the sequence of Lambda invocations, data flow between steps, and error handling. This provides visibility into the process execution.
Amazon RDS (MySQL): The relational database storing all member, MCA, service, and historical data.
AWS Secrets Manager: Securely stores and manages the database credentials, accessed via a VPC Endpoint for enhanced security.
Amazon VPC: Provides a secure, isolated network environment for the Lambda functions, RDS database, and Secrets Manager endpoint.
7. Workflow Summary
Trigger: An operator uses the Bedrock Agent or the frontend calls the POST /rosters API.
Initiation: The RosterAgentHandler Lambda starts the RosteringOrchestrator Step Function. (API calls receive an executionArn).
Data Gathering (Parallel): The Step Function invokes seld_lambda_function and get_all_available_mcas simultaneously.
Matching: The results are passed to the find_best_match Lambda, which performs data enrichment and runs the scoring algorithm.
Output: The find_best_match Lambda generates the final roster JSON, which becomes the output of the Step Function execution.
Retrieval (API): The frontend polls the GET /rosters/{executionArn} endpoint until the Step Function succeeds and the final roster is returned.
8. Benefits
Efficiency: Drastically reduces the administrative time required for daily rostering.
Optimization: Assigns MCAs based on data-driven logic, aiming for the best fit considering continuity, proximity, and language.
Consistency: Ensures the same criteria and logic are applied every day, removing subjectivity.
Improved Service Quality: Prioritizing continuity and language match leads to better member experiences.
Transparency: Provides clear justifications for each assignment, aiding supervisors in understanding the rationale.
Scalability: The serverless architecture can easily handle growth in the number of members and MCAs.
9. Current Status & Future Enhancements
The Intelligent Rostering Agent is currently functional, deployed on AWS, and successfully generating rosters based on the defined criteria. Both the Bedrock Agent interface and the asynchronous API for frontend integration are operational.
Potential future enhancements include:
Incorporating MCA skill sets (e.g., specific medical training) into the matching criteria.
Adding member-specific preferences (e.g., preferred MCA, gender preference).
Integrating real-time traffic data for more accurate travel time estimations.
Implementing a feedback loop where member satisfaction scores influence future assignments.
