db = db.getSiblingDB("chat_history");

// --------------------
// Create collections
// --------------------

db.createCollection("chats", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["user_id", "chat_id", "created_at", "updated_at"],
      additionalProperties: false,
      properties: {
        _id: {},
        user_id: {
          bsonType: "int",
          description: "Required int user ID"
        },
        chat_id: {
          bsonType: "string",
          description: "Required chat ID"
        },
        scenario_id: {
          bsonType: ["int", "null"],
          description: "Optional int scenario ID"
        },
        title: {
          bsonType: ["string", "null"],
          description: "Optional chat title"
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
      required: ["chat_id", "seq", "role", "parts", "created_at"],
      additionalProperties: false,
      properties: {
        _id: {},
        chat_id: {
          bsonType: "string",
          description: "Required chat ID"
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
                enum: ["text", "tool_call", "status"]
              },
              payload: {
                bsonType: "object"
              },
              created_at: {
                bsonType: "date"
              }
            },
            oneOf: [
              {
                properties: {
                  kind: { enum: ["text"] },
                  payload: {
                    bsonType: "object",
                    required: ["text"],
                    additionalProperties: false,
                    properties: {
                      text: { bsonType: "string" }
                    }
                  }
                }
              },
              {
                properties: {
                  kind: { enum: ["tool_call"] },
                  type: { enum: ["data", "buffers", "restrictions"] },
                  payload: {
                    bsonType: "object",
                    required: ["execution_mode", "calls"],
                    additionalProperties: false,
                    properties: {
                      execution_mode: {
                        enum: ["sequential"]
                      },
                      calls: {
                        bsonType: "array",
                        minItems: 1,
                        items: {
                          bsonType: "object",
                          required: ["step", "tool_name", "arguments"],
                          additionalProperties: false,
                          properties: {
                            step: {
                              bsonType: "int",
                              minimum: 1
                            },
                            tool_name: {
                              bsonType: "string"
                            },
                            arguments: {
                              bsonType: "object"
                            },
                          }
                        }
                      }
                    }
                  }
                }
              },
              {
                properties: {
                  kind: { enum: ["status"] },
                  payload: {
                    bsonType: "object",
                    required: ["status", "text"],
                    additionalProperties: false,
                    properties: {
                      status: {"bsonType": "string"},
                      text: {"bsonType": "string"}
                    }
                  }
                }
              },
            ]
          }
        },
        created_at: {
          bsonType: "date",
          description: "Creation date"
        },
        updated_at: {
          bsonType: ["date", "null"],
          description: "Optional update date"
        }
      }
    }
  },
  validationAction: "error",
  validationLevel: "strict"
});