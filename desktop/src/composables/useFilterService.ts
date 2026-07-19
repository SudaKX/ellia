import { inject, shallowRef, type InjectionKey, type ShallowRef } from 'vue'

import { filterRegistry, type FilterOptions, type FilterType } from '@/filters'

export interface FilterInstance {
  instanceId: string
  filterId: string
  filterType: FilterType
  options: FilterOptions
}

export interface FilterHandle {
  instanceId: string
  filterId: string
}

export interface FilterService {
  instances: ShallowRef<FilterInstance[]>
  create: (filterType: FilterType, options?: FilterOptions) => FilterHandle
  update: (instanceId: string, options: FilterOptions) => void
  destroy: (instanceId: string) => void
  destroyAll: () => void
}

export const FilterServiceKey: InjectionKey<FilterService> = Symbol('FilterService')

export function createFilterService(): FilterService {
  const instances = shallowRef<FilterInstance[]>([])
  let idCounter = 0

  function create(filterType: FilterType, options: FilterOptions = {}): FilterHandle {
    const registration = filterRegistry[filterType]
    if (!registration) {
      throw new Error(`Unknown filter type: ${filterType}`)
    }

    const instanceId = `filter-instance-${++idCounter}`
    const filterId = `${filterType}-filter-${idCounter}`

    instances.value = [
      ...instances.value,
      {
        instanceId,
        filterId,
        filterType,
        options: { ...options },
      },
    ]

    return { instanceId, filterId }
  }

  function update(instanceId: string, options: FilterOptions) {
    instances.value = instances.value.map((instance) => {
      if (instance.instanceId !== instanceId) return instance

      return {
        ...instance,
        options: {
          ...instance.options,
          ...options,
        },
      }
    })
  }

  function destroy(instanceId: string) {
    instances.value = instances.value.filter((instance) => instance.instanceId !== instanceId)
  }

  function destroyAll() {
    instances.value = []
  }

  return {
    instances,
    create,
    update,
    destroy,
    destroyAll,
  }
}

export function useFilterService() {
  const service = inject(FilterServiceKey)
  if (!service) {
    throw new Error('FilterService is not available')
  }
  return service
}
