# With local development this API call trigger backend
curl "http://localhost:8000/blog" \
-X POST \
-H "Content-Type: application/json" \
-d '{ "topic": "cookies"}'