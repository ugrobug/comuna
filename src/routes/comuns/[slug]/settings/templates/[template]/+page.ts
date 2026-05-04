import ComunTemplatePalette from '$lib/components/comuns/ComunTemplatePalette.svelte'
import { getTemplateEditorBlocks } from '$lib/postTemplates'

export const load = async ({ parent, params }) => {
  const parentData = await parent()
  const comun = parentData.comun ?? null
  const blockOptions = Array.isArray(comun?.options?.custom_template_editor?.block_options)
    ? comun?.options?.custom_template_editor?.block_options?.length
      ? comun?.options?.custom_template_editor?.block_options
      : getTemplateEditorBlocks('movie_review').map((option) => ({
          value: option.type,
          label: option.label,
        }))
    : getTemplateEditorBlocks('movie_review').map((option) => ({
        value: option.type,
        label: option.label,
      }))

  return {
    comun,
    slug: params.slug,
    template: params.template,
    slots: {
      sidebar: {
        component: ComunTemplatePalette,
        props: {
          fieldOptions: [
            { value: 'text', label: 'Текстовое поле' },
            { value: 'select', label: 'Выпадающий список' },
            { value: 'checkbox', label: 'Чекбокс' },
          ],
          blockOptions,
        },
      },
    },
  }
}
