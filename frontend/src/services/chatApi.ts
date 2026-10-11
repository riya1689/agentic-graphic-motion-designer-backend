import type {
    AgentApiResponse,
    Attachment,
} from "../types/chat";
import { authorizedFetch, getAuthHeaders } from "./authApi";
import { getApiBaseUrl } from "./apiBase";

// ========================================
// FRONTEND <-> BACKEND API BOUNDARY
// ========================================
//
// IMPORTANT:
// UI components MUST NOT call manager/planner/
// graphic-agent directly.
//
// All backend communication goes through
// this service.
//
// Backend architecture can change later
// without changing the UI components.
// ========================================

const CHAT_ENDPOINT =
    import.meta.env.VITE_CHAT_ENDPOINT ||
    "/api/manager/execute";

interface SendPromptArgs {
    prompt: string;
    attachments?: Attachment[];
    selectedImageModel?: string;
    selectedVideoModel?: string;
}

async function serializeAttachment(attachment: Attachment) {
    const file = attachment.file;
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    const chunkSize = 0x8000;
    for (let index = 0; index < bytes.length; index += chunkSize) {
        binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
    }
    const extension = file.name.split(".").pop()?.toLowerCase();
    const mimeType = file.type || (
        extension === "svg" ? "image/svg+xml" :
        extension === "jpg" || extension === "jpeg" ? "image/jpeg" :
        "image/png"
    );
    return {
        id: attachment.id,
        type: "image",
        name: file.name,
        mime_type: mimeType,
        uri: `data:${mimeType};base64,${btoa(binary)}`,
    };
}

// ========================================
// Convert backend/transport errors into
// polite user-facing messages.
// ========================================

function getFriendlyErrorMessage(
    status: number,
    backendMessage?: string,
): string {
    const message =
        backendMessage?.toLowerCase() || "";

    // API/model rate limit
    if (
        status === 429 ||
        message.includes("rate limit") ||
        message.includes("quota") ||
        message.includes("limit reached")
    ) {
        return (
            "I’m sorry, the image generation limit has been reached. " +
            "Please try again later or use another available generation model."
        );
    }

    // Authentication problem
    if (status === 401 || status === 403) {
        return (
            "I’m sorry, the request could not be authorized. " +
            "Please check the API configuration."
        );
    }

    // Backend unavailable
    if (status >= 500) {
        return (
            "I’m sorry, the design service is temporarily unavailable. " +
            "Please try again."
        );
    }

    // Generic image-generation failure
    if (
        message.includes("image generation failed") ||
        message.includes("generation failed")
    ) {
        return (
            "I’m sorry, the image could not be generated. " +
            "Please try again or adjust your request."
        );
    }

    return (
        backendMessage ||
        "I’m sorry, I couldn’t complete the request. Please try again."
    );
}

// ========================================
// SEND USER PROMPT TO THE ORCHESTRATOR API
// ========================================

export async function sendPromptToManager({
    prompt,
    attachments = [],
    selectedImageModel,
    selectedVideoModel,
}: SendPromptArgs): Promise<AgentApiResponse> {
    try {
        const serializedAttachments = await Promise.all(
            attachments.map(serializeAttachment),
        );
        const headers: HeadersInit = {
            "Content-Type": "application/json",
        };

        const authHeaders = getAuthHeaders();
        Object.entries(authHeaders).forEach(([name, value]) => {
            if (value) headers[name] = String(value);
        });

        const response = await authorizedFetch(
            `${getApiBaseUrl()}${CHAT_ENDPOINT}`,
            {
                method: "POST",

                headers,

                body: JSON.stringify({
                    prompt,
                    selected_image_model: selectedImageModel,
                    selected_video_model: selectedVideoModel,
                    attachments: serializedAttachments,
                }),
            },
        );

        if (response.status === 401) {
            return {
                success: false,
                message: "Your session has expired. Please log in again and retry.",
                error: "Authentication required.",
                error_code: "AUTHENTICATION_REQUIRED",
            };
        }

        let result: AgentApiResponse = {
            success: false,
        };

        // ------------------------------------
        // Protect UI from invalid backend JSON
        // ------------------------------------

        try {
            result = await response.json();
        } catch {
            result = {
                success: false,
                error: "Invalid server response.",
            };
        }

        if (!response.ok || result.success === false) {
            const backendError =
                result.error ||
                result.message ||
                (typeof result.detail === "string"
                    ? result.detail
                    : Array.isArray(result.detail)
                        ? result.detail.map((item) => item.msg || item.detail || "Validation error").join("; ")
                        : undefined) ||
                "Request failed.";

            const friendlyMessage = getFriendlyErrorMessage(
                response.status,
                backendError,
            );

            return {
                success: false,
                message: friendlyMessage === backendError
                    ? backendError
                    : `${friendlyMessage} Details: ${backendError}`,

                error: backendError,

                error_code: result.error_code,
            };
        }

        return result;
    } catch (error) {
        // ------------------------------------
        // Network failure:
        // FastAPI offline, wrong port, etc.
        // ------------------------------------

        console.error(
            "[FRONTEND API] Manager request failed:",
            error,
        );

        return {
            success: false,

            message:
                "I’m sorry, I can’t connect to the design service right now. " +
                "Please make sure the server is running and try again.",

            error: "NETWORK_ERROR",
            error_code: "NETWORK_ERROR",
        };
    }
}
