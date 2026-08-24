db = db.getSiblingDB("chat_history");

if (!db.getUser("mongo")) {
  db.createUser({
    user: "mongo",
    pwd: "mongo",
    roles: [{ role: "readWrite", db: "chat_history" }]
  });
}

const chatSpaces = ["main", "synapse"];

const uuidPattern = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$";

db.createCollection("chats", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["user_id", "chat_id", "space", "next_seq", "created_at", "updated_at"],
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
        space: {
          enum: chatSpaces,
          description: "Required chat space (provider environment)"
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
                enum: [
                  "text", "tool_call", "tool_result", "status", "data", "table", "file",
                  "plan", "plan_revision", "artifact_ref", "validation", "failure"
                  , "check_plan", "requirement_resolution", "compliance_result",
                  "compliance_summary"
                ]
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
db.chats.createIndex({ user_id: 1, space: 1, updated_at: -1 });
db.chats.createIndex({ user_id: 1, space: 1, scenario_id: 1, updated_at: -1 });
db.chats.createIndex({ user_id: 1, space: 1, project_id: 1, updated_at: -1 });

db.messages.createIndex({ user_id: 1, chat_id: 1, seq: 1 }, { unique: true });
db.messages.createIndex({ user_id: 1, chat_id: 1, message_id: 1 }, { unique: true });
db.messages.createIndex({ user_id: 1, chat_id: 1, created_at: 1 });

db.createCollection("chat_contexts", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "user_id", "chat_id", "revision", "content", "updated_through_seq",
        "target_seq", "model", "prompt_version", "status", "created_at", "updated_at"
      ],
      additionalProperties: false,
      properties: {
        _id: {}, user_id: { bsonType: "string", pattern: uuidPattern },
        chat_id: { bsonType: "string", pattern: uuidPattern },
        revision: { bsonType: "int", minimum: 1 },
        content: { bsonType: "object" },
        updated_through_seq: { bsonType: "int", minimum: 1 },
        target_seq: { bsonType: "int", minimum: 1 },
        model: { bsonType: "string" }, prompt_version: { bsonType: "string" },
        status: { enum: ["ready", "failed"] },
        last_error: { bsonType: ["string", "null"] },
        created_at: { bsonType: "date" }, updated_at: { bsonType: "date" }
      }
    }
  }, validationAction: "error", validationLevel: "strict"
});

db.createCollection("chat_context_revisions", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "user_id", "chat_id", "revision", "content", "updated_through_seq",
        "target_seq", "model", "prompt_version", "status", "created_at",
        "updated_at", "archived_at"
      ],
      additionalProperties: false,
      properties: {
        _id: {}, user_id: { bsonType: "string", pattern: uuidPattern },
        chat_id: { bsonType: "string", pattern: uuidPattern },
        revision: { bsonType: "int", minimum: 1 }, content: { bsonType: "object" },
        updated_through_seq: { bsonType: "int", minimum: 1 },
        target_seq: { bsonType: "int", minimum: 1 },
        model: { bsonType: "string" }, prompt_version: { bsonType: "string" },
        status: { enum: ["ready", "failed"] },
        last_error: { bsonType: ["string", "null"] },
        created_at: { bsonType: "date" }, updated_at: { bsonType: "date" },
        archived_at: { bsonType: "date" }
      }
    }
  }, validationAction: "error", validationLevel: "strict"
});
db.createCollection("context_jobs", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: [
        "job_id", "user_id", "chat_id", "target_seq", "model", "prompt_version",
        "status", "attempts", "created_at", "updated_at"
      ],
      additionalProperties: false,
      properties: {
        _id: {}, job_id: { bsonType: "string", pattern: uuidPattern },
        user_id: { bsonType: "string", pattern: uuidPattern },
        chat_id: { bsonType: "string", pattern: uuidPattern },
        target_seq: { bsonType: "int", minimum: 1 },
        model: { bsonType: "string" }, prompt_version: { bsonType: "string" },
        status: { enum: ["pending", "leased", "completed", "failed"] },
        attempts: { bsonType: "int", minimum: 0, maximum: 3 },
        lease_owner: { bsonType: ["string", "null"] },
        lease_until: { bsonType: ["date", "null"] },
        last_error: { bsonType: ["string", "null"] },
        created_at: { bsonType: "date" }, updated_at: { bsonType: "date" }
      }
    }
  }, validationAction: "error", validationLevel: "strict"
});

db.chat_contexts.createIndex({ user_id: 1, chat_id: 1 }, { unique: true });
db.chat_context_revisions.createIndex({ user_id: 1, chat_id: 1, revision: -1 });
db.chat_context_revisions.createIndex({ archived_at: 1 }, { expireAfterSeconds: 604800 });
db.context_jobs.createIndex(
  { user_id: 1, chat_id: 1, target_seq: 1, prompt_version: 1 },
  { unique: true }
);
db.context_jobs.createIndex({ status: 1, lease_until: 1, created_at: 1 });
