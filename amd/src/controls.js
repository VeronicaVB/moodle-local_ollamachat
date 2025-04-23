
define(['core/ajax', 'jquery',  'core/notification'], function(Ajax, $, Notification) {
    return {
        init: function() {
            //  DOM elements
            var messagesContainer = document.getElementById('local_ollamachat_messages');
            var form = document.getElementById('local_ollamachat_form');
            var textarea = document.getElementById('local_ollamachat_prompt');
            var submitButton = document.getElementById('local_ollamachat_submit');

            // Auto-adjust the height of the textarea
            textarea.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = this.scrollHeight + 'px';
            });

            // Handle Enter to send (Shift+Enter for a new line)
            textarea.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    form.dispatchEvent(new Event('submit'));
                }
            });

            form.addEventListener('submit', function(e) {
                e.preventDefault();
                var prompt = textarea.value.trim();
                if (!prompt) return;

                // Disable inputs during submission
                textarea.disabled = true;
                submitButton.disabled = true;

                addMessage('user', prompt);
                textarea.value = '';
                textarea.style.height = 'auto';

                // Show loader
                var messageId = 'local_ollamachat_msg_' + Date.now();
                addMessage('assistant', '<div class="local_ollamachat_loader"><div></div><div></div><div></div></div>', messageId);

                var promise = Ajax.call([{
                    methodname: 'local_ollamachat_ask_with_knowledge',
                    args: {
                        prompt: prompt,
                        moodlewsrestformat: 'json'
                    }
                }])[0];

                promise.done(function(response) {
                    updateMessageContent(messageId, formatResponse(response.response));
                }).fail(function(error) {
                    updateMessageContent(messageId,
                        '<div class="alert alert-danger">Error connecting to the server</div>'
                    );
                }).always(function() {
                    textarea.disabled = false;
                    submitButton.disabled = false;
                    textarea.focus();
                    scrollToBottom();
                });


            });

            function addMessage(role, content, id) {
                var messageClass = role === 'user' ? 'local_ollamachat_user_message' : 'local_ollamachat_assistant_message';
                var messageHTML = [
                    '<div class="local_ollamachat_message ' + messageClass + '"' + (id ? ' id="' + id + '"' : '') + '>',
                        '<div class="local_ollamachat_avatar">' + (role === 'user' ? '👤' : '✨') + '</div>',
                        '<div class="local_ollamachat_message_content">' + content + '</div>',
                    '</div>'
                ].join('');
                messagesContainer.insertAdjacentHTML('beforeend', messageHTML);
                scrollToBottom();
            }

            function updateMessageContent(messageId, content) {
                var message = document.getElementById(messageId);
                if (message) {
                    var contentElement = message.querySelector('.local_ollamachat_message_content');
                    if (contentElement) {
                        contentElement.innerHTML = content;
                    }
                }
            }

            function formatResponse(text) {
                if (!text) return '<div class="local_ollamachat_alert local_ollamachat_alert-info">No answer received</div>';

                // Procesar enlaces
                let formatted = text;

                // 1. Format items
                formatted = formatted.replace(/(https?:\/\/[^\s]+)/g, function(url) {
                    const cleanUrl = url.replace(/^https?:\/\/(www\.)?/, '');
                    return '<div class="local_ollamachat_link_item">' +
                           '<i class="local_ollamachat_link_icon fa fa-link"></i>' +
                           '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' +
                           url +
                           '</a></div>';
                });

                // 2. Format inline code with a specific class
                formatted = formatted.replace(/`([^`]+)`/g, '<code class="local_ollamachat_inline_code">$1</code>');

                // 3. Format code blocks with custom classes
                formatted = formatted.replace(/```(\w*)\n([^`]+)```/gs,
                    '<div class="local_ollamachat_code_container">' +
                    '<pre class="local_ollamachat_code_block"><code class="local_ollamachat_code $1">$2</code></pre>' +
                    '</div>');

                // 4. Convert line breaks while maintaining classes
                formatted = formatted.replace(/\n\n+/g, '</p><p class="local_ollamachat_paragraph">')
                                     .replace(/\n/g, '<br>');

                // 5. Ensure paragraphs have a consistent class
                if (!formatted.startsWith('<p>') && !formatted.startsWith('<div') && !formatted.startsWith('<pre')) {
                    formatted = '<p class="local_ollamachat_paragraph">' + formatted + '</p>';
                }

                return formatted;
            }

            function scrollToBottom() {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
        }
    };
});