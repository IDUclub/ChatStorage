db = db.getSiblingDB("chat_history");

if (!db.getUser("mongo")) {
  db.createUser({
    user: "mongo",
    pwd: "mongo",
    roles: [{ role: "readWrite", db: "chat_history" }]
  });
}

const uuidPattern = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$";

db.createCollection("chats", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["user_id", "chat_id", "next_seq", "created_at", "updated_at"],
      additionalProperties: false,
      properties: {
        _id: {},
        user_id: {
          bsonType: "string",
          pattern: uuidPattern,
          description: "Required user UUID from auth token"
        },
        chat_id: {
          bsonType: "string",
          pattern: uuidPattern,
          description: "Required service-generated chat UUID"
        },
        scenario_id: {
          bsonType: ["string", "int", "null"],
          description: "Optional scenario identifier"
        },
        project_id: {
          bsonType: ["string", "int", "null"],
          description: "Optional project identifier"
        },
        title: {
          bsonType: ["string", "null"],
          description: "Optional chat title"
        },
        metadata: {
          bsonType: "object",
          description: "Optional client or assistant metadata"
        },
        next_seq: {
          bsonType: "int",
          minimum: 1,
          description: "Next message sequence number in this chat"
        },
        created_at: {
          bsonType: "date",
          description: "Creation date"
        },
        updated_at: {
          bsonType: "date",
          description: "Last update date"
        }
      }
    }
  },
  validationAction: "error",
  validationLevel: "strict"
});

db.createCollection("messages", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "user_id",
        "chat_id",
        "message_id",
        "seq",
        "role",
        "parts",
        "created_at",
        "updated_at"
      ],
      additionalProperties: false,
      properties: {
        _id: {},
        user_id: {
          bsonType: "string",
          pattern: uuidPattern,
          description: "Required user UUID from auth token"
        },
        chat_id: {
          bsonType: "string",
          pattern: uuidPattern,
          description: "Required service-generated chat UUID"
        },
        message_id: {
          bsonType: "string",
          pattern: uuidPattern,
          description: "Required service-generated message UUID"
        },
        seq: {
          bsonType: "int",
          minimum: 1,
          description: "Message sequence number inside one chat"
        },
        role: {
          enum: ["user", "assistant", "system", "tool"],
          description: "Message role"
        },
        parts: {
          bsonType: "array",
          minItems: 1,
          description: "Ordered message parts",
          items: {
            bsonType: "object",
            required: ["part_seq", "kind", "payload", "created_at"],
            additionalProperties: false,
            properties: {
              part_seq: {
                bsonType: "int",
                minimum: 1
              },
              kind: {
                enum: ["text", "tool_call", "tool_result", "status", "data"]
              },
              payload: {
                bsonType: "object"
              },
              mcp_source: {
                bsonType: ["string", "null"],
                description: "Optional MCP server name that executed this tool"
              },
              created_at: {
                bsonType: "date"
              }
            }
          }
        },
        metadata: {
          bsonType: "object",
          description: "Optional model, token, trace, or client metadata"
        },
        created_at: {
          bsonType: "date",
          description: "Creation date"
        },
        updated_at: {
          bsonType: "date",
          description: "Last update date"
        }
      }
    }
  },
  validationAction: "error",
  validationLevel: "strict"
});

db.chats.createIndex({ user_id: 1, updated_at: -1 });
db.chats.createIndex({ user_id: 1, chat_id: 1 }, { unique: true });
db.chats.createIndex({ user_id: 1, scenario_id: 1, updated_at: -1 });
db.chats.createIndex({ user_id: 1, project_id: 1, updated_at: -1 });

db.messages.createIndex({ user_id: 1, chat_id: 1, seq: 1 }, { unique: true });
db.messages.createIndex({ user_id: 1, chat_id: 1, message_id: 1 }, { unique: true });
db.messages.createIndex({ user_id: 1, chat_id: 1, created_at: 1 });
