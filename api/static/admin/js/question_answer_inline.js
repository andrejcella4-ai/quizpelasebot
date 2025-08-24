(function($) {
    'use strict';
    
    $(document).ready(function() {
        console.log('Question Answer Inline JS loaded successfully!');
        console.log('jQuery version:', $.fn.jquery);
        // Функция для управления чекбоксами "Правильный ответ"
        function manageCorrectAnswerCheckboxes() {
            var questionType = $('#id_question_type').val();
            
            // Ищем все inline формы для ответов
            $('#questionanswer_set-group .inline-related').each(function(index) {
                var inlineForm = $(this);
                var checkbox = inlineForm.find('input[name$="-is_right"]');
                var deleteCheckbox = inlineForm.find('input[name$="-DELETE"]');
                
                // Пропускаем удаленные формы
                if (deleteCheckbox.is(':checked')) {
                    return;
                }
                
                if (questionType === 'text') {
                    // Для текстовых вопросов
                    if (index === 0) {
                        // Первый ответ всегда правильный для текстовых вопросов
                        checkbox.prop('checked', true);
                        checkbox.prop('disabled', true);
                        inlineForm.addClass('text-question-first-answer').removeClass('text-question-other-answer');
                        // Добавляем подсказку
                        var helpDiv = checkbox.closest('.field-is_right').find('.help-text-auto');
                        if (helpDiv.length === 0) {
                            checkbox.closest('.field-is_right').append('<div class="help-text-auto">Для текстовых вопросов первый ответ автоматически считается правильным</div>');
                        }
                    } else {
                        // Остальные ответы не могут быть правильными
                        checkbox.prop('checked', false);
                        checkbox.prop('disabled', true);
                        inlineForm.addClass('text-question-other-answer').removeClass('text-question-first-answer');
                        // Добавляем подсказку
                        var helpDiv = checkbox.closest('.field-is_right').find('.help-text-auto');
                        if (helpDiv.length === 0) {
                            checkbox.closest('.field-is_right').append('<div class="help-text-auto">Для текстовых вопросов только первый ответ может быть правильным</div>');
                        }
                    }
                } else if (questionType === 'variant') {
                    // Для вариантных вопросов
                    checkbox.prop('disabled', false);
                    inlineForm.removeClass('text-question-first-answer text-question-other-answer');
                    // Удаляем подсказку
                    checkbox.closest('.field-is_right').find('.help-text-auto').remove();
                }
            });
        }
        
        // Функция для обновления порядка после удаления
        function updateInlineOrder() {
            setTimeout(function() {
                manageCorrectAnswerCheckboxes();
            }, 100);
        }
        
        // Вызываем функцию при загрузке страницы
        setTimeout(function() {
            manageCorrectAnswerCheckboxes();
        }, 100);
        
        // Вызываем функцию при изменении типа вопроса
        $('#id_question_type').on('change', function() {
            manageCorrectAnswerCheckboxes();
        });
        
        // Наблюдатель за изменениями в DOM для обработки добавления/удаления форм
        var observer = new MutationObserver(function(mutations) {
            var shouldUpdate = false;
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList') {
                    // Проверяем, добавились или удалились inline формы
                    if (mutation.target.id === 'questionanswer_set-group' || 
                        $(mutation.target).closest('#questionanswer_set-group').length > 0) {
                        shouldUpdate = true;
                    }
                }
            });
            
            if (shouldUpdate) {
                updateInlineOrder();
            }
        });
        
        // Начинаем наблюдение за изменениями
        var targetNode = document.getElementById('questionanswer_set-group');
        if (targetNode) {
            observer.observe(targetNode, { 
                childList: true, 
                subtree: true 
            });
        }
        
        // Обработка клика по DELETE чекбоксам
        $(document).on('change', 'input[name$="-DELETE"]', function() {
            updateInlineOrder();
        });
        
        // Дополнительная обработка для кнопок добавления
        $(document).on('click', '.add-row a', function() {
            updateInlineOrder();
        });
    });
})(django.jQuery);
