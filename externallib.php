<?php
defined('MOODLE_INTERNAL') || die();
require_once($CFG->libdir . '/externallib.php');

class local_ollamachat_external extends external_api {

    // Asks the original model.
    public static function ask_ollama($prompt, $moodlewsrestformat) {
        global $USER, $DB;

        $params = self::validate_parameters(self::ask_ollama_parameters(), [
            'prompt' => $prompt,
            'moodlewsrestformat' => $moodlewsrestformat
        ]);

        $python_script = __DIR__ . '/scripts/ollama_helper.py';
        $output = shell_exec("python3 {$python_script} " . escapeshellarg($params['prompt']));
        return json_decode($output, true);
    }

    // Parameters for original function
    public static function ask_ollama_parameters() {
        return new external_function_parameters([
            'prompt' => new external_value(PARAM_TEXT, 'Prompt for Ollama'),
            'moodlewsrestformat' => new external_value(PARAM_ALPHA, 'Response format', VALUE_DEFAULT, 'json')
        ]);
    }


    // Return structure for original function
    public static function ask_ollama_returns() {
        return new external_single_structure([
            'success' => new external_value(PARAM_BOOL, 'Operation status'),
            'response' => new external_value(PARAM_RAW, 'Ollama response')
        ]);
    }

    // New knowledge function
    public static function ask_with_knowledge($prompt, $moodlewsrestformat) {
        global $CFG;

        $params = self::validate_parameters(self::ask_with_knowledge_parameters(), [
            'prompt' => $prompt,
            'moodlewsrestformat' => $moodlewsrestformat
        ]);

        $knowledge_url = get_config('local_ollamachat', 'knowledge_api_url');
        $python_script = __DIR__ . '/scripts/ollama_helper.py';

        // 1. Execute Python with robust character handling
        $command = sprintf(
            'python3 %s %s %s',
            escapeshellarg($python_script),
            escapeshellarg($params['prompt']),
            escapeshellarg($knowledge_url ?? '')
        );
        $output = shell_exec($command);

        // 2. Improved JSON decoding
        $response = json_decode($output, true);

        // 3. More flexible validation
        if (json_last_error() !== JSON_ERROR_NONE || !is_array($response)) {
            error_log("JSON decode error: " . json_last_error_msg());
            error_log("Raw output: " . $output);
            throw new moodle_exception('invalidresponse', 'local_ollamachat', '', null, $output);
        }

        // 4. Ensure minimum structure
        if (!array_key_exists('success', $response)) {
            $response['success'] = false;
        }

        // 5. Correct encoding if necessary
        if (is_string($response['response'])) {
            $response['response'] = mb_convert_encoding($response['response'], 'UTF-8', 'UTF-8');
        }

        return $response;
    }

    // This model has access to the KB content
    public static function ask_with_knowledge_parameters() {
        return new external_function_parameters([
            'prompt' => new external_value(PARAM_TEXT, 'Question'),
            'moodlewsrestformat' => new external_value(PARAM_ALPHA, 'Format of the answer', VALUE_DEFAULT, 'json') // Ohterwise you get an XML
        ]);
    }

    public static function ask_with_knowledge_returns() {
        return new external_single_structure([
            'success' => new external_value(PARAM_BOOL, 'Operation status'),
            'response' => new external_value(PARAM_RAW, 'Ollama answer'),
            'sources' => new external_multiple_structure(
                new external_value(PARAM_URL, 'URL'),
                'Knowledge base source', VALUE_OPTIONAL
            )
        ]);
    }



}